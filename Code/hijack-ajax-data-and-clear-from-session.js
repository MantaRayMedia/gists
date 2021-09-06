
    function deserializeToObject (){
      let result = {};
      this.replace(
        new RegExp("([^?=&]+)(=([^&]*))?", "g"),
        function($0, $1, $2, $3) { result[$1] = $3; }
      )
      return result;
    }
    String.prototype.deserializeToObject = deserializeToObject;

    serializeObject = function(obj) {
      let str = [];
      for (const p in obj)
        if (obj.hasOwnProperty(p)) {
          str.push(encodeURIComponent(p) + "=" + obj[p]);
        }
      return str.join("&");
    };

    // Get ajax views instance name
    const view_to_hijack = "resources_search";

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

    const beforeSend = Drupal.ajax.prototype.beforeSend;
    if (view && view_dom_id && view_name) {
      Drupal.ajax.prototype.beforeSend = function (xmlhttprequest, options) {
        if (options.extraData && options.extraData.view_name && options.extraData.view_name === view_to_hijack) {
          const fieldsToClear = [
            'field_tag%5B%5D', 'field_resource_type%5B%5D', 'field_organisation%5B%5D', 'field_resource_country%5B%5D',
            'field_contributor'
          ];
          let form_values = options.data.deserializeToObject();

          var filtersToClear = [];

          Object.entries(fieldsToClear).forEach(([key, value]) => {
            if (!form_values.hasOwnProperty(value)) {
              value = value.replace('%5B%5D', '');
              filtersToClear.push(value);
            }
          })

          if (filtersToClear.length !== 0){
            $.ajax({
              type: "GET",
              url: window.location.origin + "/ajax/unset-session-parameter?filter="+filtersToClear, //custom made endpoint, check module mrm_view_session_storage in alnap project
              dataType: "json",
              async:false,
              success: function(data) {
              }
            });
          }
        }

        beforeSend.call(this, xmlhttprequest, options);
        $(document).trigger('beforeSend');
      }
    }
