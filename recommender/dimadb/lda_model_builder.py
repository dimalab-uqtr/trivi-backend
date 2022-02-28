import os

# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommender.settings")

import django
import datetime
from gensim.matutils import cossim
from gensim import corpora, models, similarities
from gensim.models import CoherenceModel, ldamodel
from gensim.parsing.porter import PorterStemmer
from nltk.tokenize import RegexpTokenizer
from django.apps import apps
import nltk 
from stop_words import get_stop_words
import re

# django.setup()
from dimadb.models import Events, Products, LdaSimilarityVersion, LdaSimilarity


def load_data(table_name):
    Model = apps.get_model(app_label='dimadb', model_name=table_name)
    docs = list(Model.objects.all().order_by('-created_at'))
    data = [str(item.description) for item in docs]

    if len(data) == 0:
        print('There is no data of cultural product')

    return docs, data

class LdaModelManager(object):

    def __init__(self, min_sim=0.1):
        self.dirname, self.filename = os.path.split(os.path.abspath(__file__))
        self.lda_path = self.dirname

        self.min_sim = min_sim
        self.NUM_OF_TOPICS = 11 # The default value of num of topics (best)

    def set_num_topics(self, num_of_topics):
        self.NUM_OF_TOPICS = num_of_topics

    def get_latest_lda_model(self, table_name, retrain=False, populate_sims=False):
        if LdaSimilarityVersion.objects.filter(item_type=table_name).exists():
            latest_lda = LdaSimilarityVersion.objects.filter(item_type=table_name).latest('created_at')
        else:
            latest_lda = None
            
        if latest_lda != None and not retrain:
            self.model = models.ldamodel.LdaModel.load(os.path.join(self.lda_path, 'model_recommend', 'model_' + table_name + '.lda'))
            self.corpus = corpora.MmCorpus(os.path.join(self.lda_path, 'model_recommend', 'corpus_' + table_name + '.mm'))

            if populate_sims:
                docs, data = load_data(table_name)
                self.save_similarity(docs, table_name)
        else:
            self.train_model(table_name=table_name) 

    def train_model(self, data=None, docs=None, table_name=None):
        if data is None:
            docs, data = load_data(table_name=table_name)
    
        self.build_model(data, docs, self.NUM_OF_TOPICS, table_name)

    def build_model(self, data, docs, n_topics, table_name):
        texts = list()
        tokenizer = RegexpTokenizer('\w+')
        stemmer = PorterStemmer()

        for d in data:
            # Preprocessing the text
            final_preprocess_tokens = self.preprocessing(tokenizer, stemmer, d)
            texts.append(final_preprocess_tokens)

        dictionary = corpora.Dictionary(texts)
        corpus = [dictionary.doc2bow(text) for text in texts]       
        lda_model = models.ldamodel.LdaModel(corpus=corpus, id2word=dictionary, num_topics=n_topics, random_state=100)
        num_docs = len(docs)

        self.model = lda_model
        self.corpus = corpus

        # Save the model and update the database
        self.save_lda_model(lda_model, corpus, dictionary, num_docs, table_name)
        self.save_similarity(docs, table_name)

    def save_lda_model(self, lda_model, corpus, dictionary, n_docs, table_name):
        current_time = datetime.datetime.now()
        current_time_str = current_time.strftime('%Y%m%d_%H%M%S_')

        # Create the path 
        # index_path = os.path.relpath(os.path.join(self.lda_path, 'index.lda'))
        model_path = os.path.relpath(os.path.join(self.lda_path, 'model_recommend', 'model_' + table_name + '.lda'))
        dictionary_path = os.path.relpath(os.path.join(self.lda_path, 'model_recommend', 'dict_' + table_name + '.lda'.format(current_time_str)))
        corpus_path = os.path.relpath(os.path.join(self.lda_path, 'model_recommend', 'corpus_' + table_name + '.mm'.format(current_time_str)))
        lda_model.save(model_path)
        dictionary.save(dictionary_path)
        corpora.MmCorpus.serialize(corpus_path, corpus)
        
        # Save all the paths with some data of the version of the model in the database 
        LdaSimilarityVersion.objects.create(
            created_at=current_time,
            n_topics=self.NUM_OF_TOPICS,
            n_products=n_docs,
            item_type=table_name
        )

    def save_similarity(self, docs, table_name):
        latest_version = LdaSimilarityVersion.objects.filter(item_type=table_name).latest('-created_at')

        # Map each docs with the corpus
        events = [[docs[i], self.corpus[i]] for i in range(0, len(docs))]
  
        # Create lists to optimize creation and updates for records in the databse
        updated_records = list()
        created_records = list()

        # Looping through each pair of product and calculate the similarity
        for source_index in range(0, len(events)-1):
            for target_index in range(source_index + 1, len(events)):
                print(source_index, target_index)
                source_record = events[source_index]
                target_record = events[target_index]

                # Cosine similarity
                sim = cossim(
                    self.model.get_document_topics(source_record[1], minimum_probability=0), 
                    self.model.get_document_topics(target_record[1], minimum_probability=0)
                    )

                if (float(sim) >= 0.5):
                    source = source_record[0]
                    target = target_record[0]
                    
                    try:
                        
                        # First try updating the existing records.
                        u_record = LdaSimilarity.objects.get(source=source.id, target=target.id, item_type=table_name)
                        u_record.similarity = float(sim)
                        u_record.version = latest_version
                        updated_records.append(u_record)
                    except LdaSimilarity.DoesNotExist:
                        
                        # If there is no record, create a new records. 
                        c_record = LdaSimilarity(source=source.id, target=target.id, item_type=table_name, similarity=float(sim), version=latest_version)
                        created_records.append(c_record)
            
        # Proceed the database transaction/query here.
        if len(created_records) > 0:
            LdaSimilarity.objects.bulk_create(created_records)

        if len(updated_records) > 0:
            LdaSimilarity.objects.bulk_update(updated_records, fields=['similarity', 'version'])

        # Clear all the zero-similarity
        LdaSimilarity.objects.filter(similarity=0).delete()

    @staticmethod
    def remove_stopwords(tokenized_data):

        fr_stop = get_stop_words('french')

        stopped_tokens = [token for token in tokenized_data if token not in fr_stop]
        return stopped_tokens

    def preprocessing(self, tokenizer, stemmer, doc):
        
        # Converting the document to lowercase
        raw = doc.lower()
        # Remove website and email
        raw = re.sub("((\S+)?(http(s)?)(\S+))|((\S+)?(www)(\S+))|((\S+)?(\@)(\S+)?)", " ", raw)
        raw = re.sub("[^a-zA-Z ]", "", raw)

        # Steming 
        stemmed_doc = stemmer.stem_sentence(raw)     
        # Tokenize the document
        tokens = tokenizer.tokenize(stemmed_doc)

        # Remove Stopwords
        non_stopword_tokens = self.remove_stopwords(tokens)  

        # Retrieve only NOUN and VERB tokens
        # print(nltk.__version__)
        # print('NLTK:', nltk.pos_tag(['hello', 'but']))
        # only_noun_verb_tokens = [ w for (w, pos) in nltk.pos_tag(non_stopword_tokens) if pos.startswith('NN') or pos.startswith('VB')]


        # Get the finalized tokens here.
        final_tokens = non_stopword_tokens

        return final_tokens

