const API_KEY='culturemauricie2022'
const IP_DOMAIN='http://3.129.66.167:8000'


async function getRecommendItems(url) {
    var recommendItems = []
    if (url) {
        recommendItems = await fetch(IP_DOMAIN + '/dimadb/get-list-recommend/?' + url, {
            method: 'GET',
            headers: {
                Authorization: `Bearer ${API_KEY}`,
            },
        }).then(result => result.json())
        .then(result => result.items)
        .catch(err => [])
    }

    return recommendItems
}

function getListView(containerId, results, itemType, recommendType) {
    results.then((recommendItems) => {
        if (recommendItems.length) {
            title = `Les ${itemType == 'events' ? 'événements' : 'articles'}`
        
            if (recommendType == 0) {
                title += ' les plus populaires'
            } else if (recommendType == 1) {
                title += ' à venir'
            } else {
                title += ' connexes'
            }
        
            document.getElementById(containerId).innerHTML += `
                <div class="recommend">
                    <h2 class="recommend-title">${title}</h2>
                    <div class="recommend-content" id="${title}">
                    </div>
                </div>
            `
        
            for (item of recommendItems) {
                document.getElementById(title).innerHTML += `
                    <div class="recommend-container">
                        <img src="${item.img}" class="recommend-image"/>
                        <p class="recommend-name">
                            ${itemType == 'events' ? item.event_name : item.product_name}
                        </p>
                        ${itemType == 'events' ? `<div class="recommend-time">
                            <div>${item.end_date.substring(0,10)} - ${item.location_name}</div>
                        </div>` : ''}
                        <div class="recommend-type">
                            <div>${itemType == 'events' ? item.event_type.toUpperCase() : item.product_type.toUpperCase()}</div>
                        </div>
                        <a href="${item.url}" class="zoom">
                            En savoir plus &#x2192;
                        </a>
                    </div>
                `
            }
        }
    })
}

function generateRecommendAPI(itemType='', level='', domain='', itemId='', recommendType='', quantity=0) {
    var api = '';
    
    api += 'itemType=' + itemType;
    api += '&level=' + level;
    api += '&quantity=' + quantity;

    if (domain)
        api += '&domain=' + domain;
    if (itemId)
        api += '&itemId=' + itemId;

    if (recommendType == 0)
        api = api + '&recommendType=Most popular';
    else if (recommendType == 1)
        api = api + '&recommendType=Upcoming';

    
    return api;
}


function getItemType(locationUrl) {
    const articleTags = ['magazine', 'product'];
    const eventTags = ['evenements', 'event'];
    const locationParts = locationUrl.split('/'); 
    var itemType = '';

    for (const tag of articleTags) {
        if (locationParts.includes(tag)) {
            itemType = 'products';
            break;
        }
    }
    
    for (const tag of eventTags) {
        if (locationParts.includes(tag)) {
            itemType = 'events';
            break;
        }
    }

    return itemType;
}


function getDomain(itemType, locationUrl) {
    const articleTypes = ['arts-de-la-scene', 'arts-mediatiques', 'arts-visuels', 'litterature', 'metiers-dart', 'musees', 'patrimoine'];
    const eventTypes = ['chanson', 'humour', 'cinema', 'musique', 'varietes'];
    const locationParts = locationUrl.split('/'); 
    var domain = '';

    if (itemType == 'products') {
        for (const type of articleTypes) {
            if (locationParts.includes(type)) {
                domain = type;
                break;
            }
        }
    } else if (itemType == 'events') {
        for (const type of eventTypes) {
            if (locationParts.includes(type)) {
                domain = type;
                break;
            }
        }
    }
    return domain;
}


function getRecommendLevel(domain, locationUrl) {
    const articleTags = ['magazine', 'product'];
    const eventTags = ['evenements', 'event'];
    const locationParts = locationUrl.split('/'); 
    const lastLocationPart = locationParts[locationParts.length - 1];
    var level = '';

    if (lastLocationPart == domain && domain != '') {
        level = 'Domain'
    } else if (lastLocationPart != '' && !eventTags.includes(lastLocationPart) && !articleTags.includes(lastLocationPart)) {
        level = 'Item'
    } else {
        level = 'Homepage'
    }
    return level;
}


function getItemId(level, locationUrl) {
    const locationParts = locationUrl.split('/'); 
    const lastLocationPart = locationParts[locationParts.length - 1];
    var itemId = '';

    if (level == 'Item')
        itemId = lastLocationPart;

    return itemId;
}

function getMostPopularItems(containerId, itemType='', level='', domain='', quantity=0) {
    const api = generateRecommendAPI(itemType, domain, level, '', 0, quantity);
    const items = getRecommendItems(api);
    getListView(containerId, items, itemType, 0);
}

function getUpComingItems(containerId, itemType='', level='', domain='', quantity=0) {
    const api = generateRecommendAPI(itemType, domain, level, '', 1, quantity);
    const items = getRecommendItems(api);
    getListView(containerId, items, itemType, 1);
}

function getSimilarItems(containerId, itemType='', itemId='', quantity=0) {
    const api = generateRecommendAPI(itemType, '', 'Item', '', 2, quantity);
    const items = getRecommendItems(api);
    getListView(containerId, items, itemType, 2);
}

