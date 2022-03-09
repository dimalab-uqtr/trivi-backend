async function getRecommendItems(url, itemType, recommendType) {
  var recommendItems = {};
  if (url) {
    recommendItems = await fetch(
      IP_DOMAIN + "/dimadb/get-list-recommend/?" + url,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${API_KEY}`,
        },
      }
    )
      .then((result) => result.json())
      .then((result) => {
         return {
            'itemType': itemType,
            'recommendType': recommendType,
            'items': result.items
        }
        })
      .catch((err) => []);
  }

  return recommendItems;
}


function getListView(containerId, res) {
    const recommendItems = res.items;
    const itemType = res.itemType;
    const recommendType = res.recommendType;
    if (recommendItems.length) {
      title = `Les ${itemType == "events" ? "événements" : "articles"}`;

      if (recommendType == "Most popular") {
        title += " les plus populaires";
      } else if (recommendType == "Upcoming") {
        title += " à venir";
      } else {
        title += " connexes";
      }

      document.getElementById(containerId).innerHTML += `
                <div class="recommend">
                    <h2 class="recommend-title">${title}</h2>
                    <div class="recommend-content" id="${title}">
                    </div>
                </div>
            `;

      for (item of recommendItems) {
        document.getElementById(title).innerHTML += `
                    <div class="recommend-container">
                        <img src="${item.img}" class="recommend-image"/>
                        <p class="recommend-name">
                            ${
                              itemType == "events"
                                ? item.event_name
                                : item.product_name
                            }
                        </p>
                        ${
                          itemType == "events"
                            ? `<div class="recommend-time">
                            <div>${item.next_date ? item.next_date.substring(0, 10) + "-" + item.location_name : item.location_name}</div>
                        </div>`
                            : ""
                        }
                        <div class="recommend-type">
                            <div>${
                              itemType == "events"
                                ? item.event_type.toUpperCase()
                                : item.product_type.toUpperCase()
                            }</div>
                        </div>
                        <a href="${item.url}" class="zoom">
                            En savoir plus &#x2192;
                        </a>
                    </div>
                `;
      }
    }
}

function generateRecommendAPI(
  itemType = "",
  level = "",
  domain = "",
  itemId = "",
  recommendType = "",
  quantity = 0
) {
  var api = "";

  api += "itemType=" + itemType;
  api += "&level=" + level;
  api += "&quantity=" + quantity;

  if (domain) api += "&domain=" + domain;
  if (itemId) api += "&itemId=" + itemId;

  if (recommendType != "Similar") api = api + "&recommendType=" + recommendType;

  return api;
}

function getItemType(locationUrl) {
  const articleTags = ["magazine", "product"];
  const eventTags = ["evenements", "event"];
  const locationParts = locationUrl.split("/");
  var itemType = "";

  for (const tag of articleTags) {
    if (locationParts.includes(tag)) {
      itemType = "products";
      break;
    }
  }

  for (const tag of eventTags) {
    if (locationParts.includes(tag)) {
      itemType = "events";
      break;
    }
  }

  return itemType;
}

function getDomain(itemType, locationUrl) {
  const articleTypes = [
    "arts-de-la-scene",
    "arts-mediatiques",
    "arts-visuels",
    "litterature",
    "metiers-dart",
    "musees",
    "patrimoine",
  ];
  const eventTypes = ["chanson", "humour", "cinema", "musique", "varietes"];
  const locationParts = locationUrl.split("/");
  var domain = "";

  if (itemType == "products") {
    for (const type of articleTypes) {
      if (locationParts.includes(type)) {
        domain = type;
        break;
      }
    }
  } else if (itemType == "events") {
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
  const articleTags = ["magazine", "product"];
  const eventTags = ["evenements", "event"];
  const locationParts = locationUrl.split("/");
  const lastLocationPart = locationParts[locationParts.length - 1];
  var level = "";

  if (lastLocationPart == domain && domain != "") {
    level = "Domain";
  } else if (
    lastLocationPart != "" &&
    !eventTags.includes(lastLocationPart) &&
    !articleTags.includes(lastLocationPart)
  ) {
    level = "Item";
  } else {
    level = "Homepage";
  }
  return level;
}

function getItemId(level, locationUrl) {
  const locationParts = locationUrl.split("/");
  const lastLocationPart = locationParts[locationParts.length - 1];
  var itemId = "";

  if (level == "Item") itemId = lastLocationPart;

  return itemId;
}

function getMostPopularItems(
  itemType = "",
  level = "",
  domain = "",
  quantity = 0
) {
  const recommendType = "Most popular";
  const api = generateRecommendAPI(
    itemType,
    level,
    domain,
    "",
    recommendType,
    quantity
  );
  const items = getRecommendItems(api, itemType, recommendType);

  return items;
}

function getUpComingItems(
  itemType = "",
  level = "",
  domain = "",
  quantity = 0
) {
  const recommendType = "Upcoming";
  const api = generateRecommendAPI(
    itemType,
    level,
    domain,
    "",
    recommendType,
    quantity
  );
  const items = getRecommendItems(api, itemType, recommendType);

  return items;
}

function getSimilarItems(itemType = "", itemId = "", quantity = 0) {
  const recommendType = "Similar";
  const api = generateRecommendAPI(
    itemType,
    "Item",
    "",
    "",
    recommendType,
    quantity
  );
  const items = getRecommendItems(api);

  return items;
}

async function getRecommend(url, bearerToken) {
  var recommendItems = {};
  if (url) {
    recommendItems = await fetch(url,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${bearerToken}`,
        },
      }
    )
      .then((result) => result.json())
      .then((result) => {
          return {
            'itemType': result.itemType,
            'recommendType': result.recommendType,
            'items': result.items
        }
        })
      .catch((err) => []);
  }

  return recommendItems;
}


async function getRecommendation(url, bearerToken) {
  var recommendItems = [];
  if (url) {
    recommendItems = await fetch(url + '/?url=' + window.location.href,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${bearerToken}`,
        },
      }
    )
      .then((result) => result.json())
      .then((result) => {return result})
      .catch((err) => []);
  }

  return recommendItems;
}


function getListViews(recommendations) {
  if (Array.isArray(recommendations)) {
    for (var idx=0; idx < recommendations.length; idx++) {
      const res = recommendations[idx];
      const recommendItems = res.items;
      const itemType = res.itemType;
      const recommendType = res.recommendType;
      if (recommendItems.length) {
        title = `Les ${itemType == "events" ? "événements" : "articles"}`;
  
        if (recommendType == "Most popular") {
          title += " les plus populaires";
        } else if (recommendType == "Upcoming") {
          title += " à venir";
        } else {
          title += " similaires";
        }
        var recommendDivId = `recommendation-${idx}`
        document.getElementById("recommendations").innerHTML+= `<div id=${recommendDivId}></div>`
        document.getElementById(recommendDivId).innerHTML += `
                  <div class="recommend">
                      <h2 class="recommend-title">${title}</h2>
                      <div class="recommend-content" id="${title}">
                      </div>
                  </div>
              `;
  
        for (item of recommendItems) {
          document.getElementById(title).innerHTML += `
                      <div class="recommend-container">
                          <img src="${item.img}" class="recommend-image"/>
                          <p class="recommend-name">
                              ${
                                itemType == "events"
                                  ? item.event_name
                                  : item.product_name
                              }
                          </p>
                          ${
                            itemType == "events"
                              ? `<div class="recommend-time">
                              <div>${item.next_date ? item.next_date.substring(0, 10) + "-" + item.location_name : item.location_name}</div>
                          </div>`
                              : ""
                          }
                          <div class="recommend-type">
                              <div>${
                                itemType == "events"
                                  ? item.event_type.toUpperCase()
                                  : item.product_type.toUpperCase()
                              }</div>
                          </div>
                          <a href="${item.url}" class="zoom">
                              En savoir plus &#x2192;
                          </a>
                      </div>
                  `;
        }
      }
    }
  }
}