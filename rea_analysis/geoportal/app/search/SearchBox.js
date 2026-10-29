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
        "dojo/on",
        "dojo/keys",
        "dojo/dom-class",
        "dojo/topic",
        "app/context/app-topics",
        "dojo/text!./templates/SearchBox.html",
        "dojo/i18n!app/nls/resources",
        "app/search/SearchComponent",
        "app/search/QClause",
        "app/etc/util"], 
function(declare, lang, on, keys, domClass, topic, appTopics,
         template, i18n, SearchComponent, QClause, util) {
  
  var oThisClass = declare([SearchComponent], {

    i18n: i18n,
    templateString: template,
    
    useSimpleQueryString: null,

    postCreate: function() {
      this.inherited(arguments);
      this.own(on(this.searchTextBox,"keyup",lang.hitch(this,function(evt) {
        if (evt.keyCode === keys.ENTER) this.search('search');
      })));

      topic.subscribe(appTopics.SetSearchQueryFieldValue, lang.hitch(this, function(params) {
        this.searchTextBox.value = String(params.value);
        if (params.search) {
          topic.publish(appTopics.SortByField, 'sort-by-relevance');
          this.search();
        }
      }));
    },
    
    /* SearchComponent API ============================================= */
    
    appendQueryParams: function(params) {
     	var v = this.searchTextBox.value;
	
		var tempObj = [];
		var csdi_filter = sessionStorage['csdi-filter'];
		if (csdi_filter) {
			if (JSON.parse(csdi_filter).length) tempObj = JSON.parse(csdi_filter);
			else tempObj.push(JSON.parse(csdi_filter))
		}
		var checkSearchBoxQuery = tempObj.find(x => x.field == 'bool');
		var checkRequestParam = util.getRequestParam("key") ? true : false;
		
		if (v==null || lang.trim(v).length <= 0) {
			//v= location.search.match(/key=([\w\-]+)/) ? RegExp.$1 : null;
			v = util.getRequestParam("key");
			this.searchTextBox.value = v;
		}

		if (v !== null && lang.trim(v).length > 0 || checkRequestParam) {
			var tipPattern = i18n.search.appliedFilters.tipPattern;
			var tip = tipPattern.replace("{type}", i18n.search.searchBox.search).replace("{value}", v);
			var query = null, useSimpleQueryString = this.useSimpleQueryString;

			// Filter special character ONLY for Keyword search
			var displayVal = v;

			// If exactly search ? by double quote
			// ==========================================

			if (typeof useSimpleQueryString === "undefined" || useSimpleQueryString === null) {
				useSimpleQueryString = AppContext.appConfig.search.useSimpleQueryString;
			}
			if (useSimpleQueryString) {
				query = {"simple_query_string": {
					"analyze_wildcard": true,
					"query": v
				}};
			} else {
				var esQuery = util.getESQuery(v);
				query = esQuery;
			}

			//alert('query-->' + JSON.stringify(query));
			var qClause = new QClause({
				label: displayVal,
				tip: tip,
				parentQComponent: this,
				removable: true,
				scorable: true,
				query: query
			});
			this.activeQClauses = [qClause];
			this.appendQClauses(params);
		} else if (checkSearchBoxQuery) {
			topic.publish(appTopics.SortByField, 'sort-by-relevance');
			var queryObj = tempObj.find(x => x.field == 'bool');
			var displayVal = queryObj.value;
			var esQuery = util.getESQuery(queryObj.value);
			var query = esQuery;
			var qClause = new QClause({
				label: displayVal,
				tip: tip,
				parentQComponent: this,
				removable: true,
				scorable: true,
				query: query
			});
			this.activeQClauses = [qClause];
			this.appendQClauses(params);
		} else {
			this.activeQClauses = null;
		}
    },
    
    whenQClauseRemoved: function(qClause) {
      if (this === qClause.parentQComponent) {
        this.searchTextBox.value = "";
      }
    },
	
	_onSearchButtonClick: function() {
		this.search('search');
	}

  });

  return oThisClass;
});