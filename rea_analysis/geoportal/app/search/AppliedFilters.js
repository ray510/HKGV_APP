/* See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * Esri Inc. licenses this file to You under the Apache License, Version 2.0
 * (the "License"); you may not use this file except in compliance with
 * the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
define(["dojo/_base/declare",
        "dojo/_base/lang",
        "dojo/_base/array",
        "dojo/dom-construct",
        "dojo/on",
        "dojo/query",
        "dojo/dom",
        "dojo/dom-class",
        "dojo/topic",
        "app/context/app-topics",
        "dojo/text!./templates/AppliedFilters.html",
        "dojo/i18n!app/nls/resources",
        "app/search/SearchComponent",
        "app/search/AppliedFilter",
         "app/etc/util"],
function(declare, lang, array, domConstruct, on, query, dom, domClass, topic, appTopics, template, i18n, SearchComponent, AppliedFilter, Util) {

  var oThisClass = declare([SearchComponent], {

    i18n: i18n,
    templateString: template,

    allowMyContent: true,
    autoExpand: true,
    label: i18n.search.appliedFilters.label,
    open: false,

    // clearAllNode: null,
    myContentNode: null,
    myContentCheckbox: null,

    _appliedFilters: null,

    postCreate: function() {
      this.inherited(arguments);
      if (this.allowMyContent) this.addMyContent();
      this._appliedFilters = [];
    },

    addMyContent: function() {
      var self = this;
      var span = this.myContentNode = domConstruct.create("span",{
        "class": "my-content-option",
      },this.filters);
      var id = this.id+"_cbx_";
      var checkbox = this.myContentCheckbox = domConstruct.create("input",{
        id: id,
        type: "checkbox",
        onclick: function(e) {
          e.stopPropagation();
          self.search();
        }
      },span);
      var label = domConstruct.create("label",{
        "for": id,
        innerHTML: i18n.search.appliedFilters.myContent,
        onclick: function(e) {
          e.stopPropagation();
        }
      },span);
      this.myContentNode.style.display = "none";
    },

    /*
    count: function() {
      var n = 0;
      array.forEach(query(".g-applied-filter", this.filtersNode),function(child){
        n++;
      });
      return n;
    },
    */

    destroyEntries: function() {
      for (const appliedFilter of this._appliedFilters) {
        appliedFilter.destroyRecursive(false);
      }
      this._appliedFilters.length = 0;
    },

    _clearAllLinkClick: function() {
      topic.publish(appTopics.SetSearchQueryFieldValue, { value: '' });
      this.destroyEntries();
      this.clearAllLinkNode.hidden = true;
      topic.publish(appTopics.ClearAllSearchFilters, {});
      topic.publish(appTopics.ShowSearchResultsView, {});
    },

    /* SearchComponent API ============================================= */

    appendQueryParams: function(params) {
	
	  //console.warn('AppFilter search ?--------->', location.search);
	
      if (this.myContentNode && AppContext.appUser.isPublisher() && this.myContentCheckbox.checked) {
        var query = {"term": {sys_owner_s: AppContext.appUser.getUsername()}};
        if (!params.queries) params.queries = [];
        params.queries.push(query);
        params.wasMyContent = true
      } 
   
      //console.warn("AppFilter3 ----->",params);
    },

    processResults: function(searchResponse) {
      //var prevCount = this.count();
      this.destroyEntries();
      if (!this.searchPane) return;
      var hasRemovable = false, hasViewable = false;
      var entriesNode = this.entriesNode;
      var appliedFilters = this._appliedFilters;
      var components = this.searchPane.getSearchComponents();
      array.forEach(components,function(component){
        array.forEach(component.activeQClauses,function(qClause){
          if (qClause.viewable) {
            hasViewable = true;
            if (qClause.removable) hasRemovable = true;
            var af = new AppliedFilter({qClause: qClause});
            if (Object.keys(qClause.query) == 'term') domClass.add(af.domNode, 'g-applied-filter--filter');
            domConstruct.place(af.domNode, entriesNode, "first");
            qClause.onChange(true);
            appliedFilters.push(af);
          }
        });
      });
      var showMyContent = this.myContentNode && AppContext.appUser.isPublisher();
      //if (hasRemovable) this.dropPane.setDisplayTools(true);
      // if (showMyContent || hasViewable) this.dropPane.setDisplayTools(true);
      // else this.dropPane.setDisplayTools(false);
      if (showMyContent) this.myContentNode.style.display = "";
      else this.myContentNode.style.display = "none";

      this.clearAllLinkNode.hidden = !hasViewable;
      /*
      if (hasViewable) {
        this.clearAllLinkNode.style.display = "";
        // query the filtersNode height and adjust the search results pane to fit in the space
        //var filtersHeight = query(".g-applied-filters")[0].clientHeight;
        //query(".g-search-results-pane").style("height", "calc(100% - " + (filtersHeight + 32) +"px)");
      }
      else {
        this.clearAllLinkNode.style.display = "none";
        // reset the search results pane
        //query(".g-search-results-pane").style("height", "calc(100% - 32px)");
      }

      if (this.autoExpand) {
        var count = this.count();
        // if (prevCount === 0 && count > 0) {
        //   this.dropPane.set("open",true);
        // } else if (prevCount > 0 && count === 0) {
        //   this.dropPane.set("open",false);
        // }
      }
      */
    }

  });

  return oThisClass;
});
