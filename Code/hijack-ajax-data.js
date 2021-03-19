/**
 * Convert Object URL parameters
 *
 * in: {foo: "a b", bar: "c"}
 * out: foo=a+b&bar=c
 */
serializeObject = function(obj) {
  let str = [];
  for (const p in obj) {
    if (obj.hasOwnProperty(p)) {
      str.push(encodeURIComponent(p) + "=" + encodeURIComponent(obj[p]));
    }
  }
  return str.join("&");
}

/**
 * Convert URL parameters to Object
 *
 * in: foo=a&bar=b
 * out: {foo: "a", bar: "b"}
 */
function deserializeToObject (){
  let result = {};
  this.replace(
    new RegExp("([^?=&]+)(=([^&]*))?", "g"),
    function($0, $1, $2, $3) { result[$1] = $3; }
  )
  return result;
}

// create new prototype
String.prototype.deserializeToObject = deserializeToObject;

// OVERRIDE data for specific view only !
// if want to do same on all ajax calls, just ignore the part for getting the name

let pastFulltextSearch = '';
const view_to_hijack = "conf_abstracts_search";

// Get ajax views instance name
const views = Drupal.settings.views.ajaxViews;
let view = undefined;
let view_dom_id = undefined;
let view_name = undefined;

for (let viewsName in views) {
  if (views.hasOwnProperty(viewsName)) {
    if (views[viewsName]['view_display_id'] === "page" && views[viewsName]['view_name'] === view_to_hijack) {
      view = views[viewsName];
      view_name = viewsName;
      view_dom_id = view["view_dom_id"];
    }
  }
}

// We have to override the actual PROTOTYPE not the view, because it does not fire every time outside of prototype !!
const beforeSend = Drupal.ajax.prototype.beforeSend;
if (view && view_dom_id && view_name) {
  Drupal.ajax.prototype.beforeSend = function (xmlhttprequest, options) {
    if (options.extraData && options.extraData.view_name && options.extraData.view_name === view_to_hijack) {
      const fieldsToClear = [
        'countries%5B%5D', 'field_conference_selective%5B%5D', 'field_topics_selective%5B%5D', 'languages%5B%5D',
        'region%5B%5D', 'type%5B%5D', 'year%5B%5D'
      ];
      let form_values = options.data.deserializeToObject();
      let reduced = {};

      if (form_values.hasOwnProperty('search_api_views_fulltext') &&
        form_values['search_api_views_fulltext'] !== pastFulltextSearch &&
        form_values['search_api_views_fulltext'] !== '')
      {
        pastFulltextSearch = form_values['search_api_views_fulltext'];
        Object.entries(form_values).forEach(([key, value]) => {
          if (fieldsToClear.indexOf(key) === -1) {
            if (key === 'sort_by') {
              value = 'search_api_relevance';
            }
            reduced[key] = value;
          }
        })

        options.data = $.param(reduced);
      } else {
        pastFulltextSearch = '';
      }
    }

    beforeSend.call(this, xmlhttprequest, options);
    $(document).trigger('beforeSend');
  }
}