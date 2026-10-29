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
  "dojo/topic",
  "app/context/app-topics",
  "dojo/text!./templates/TermsAggregation.html",
  "dojo/i18n!app/nls/resources",
  "app/search/SearchComponent",
  "app/search/DropPane",
  "app/search/QClause",
  "app/search/TermsAggregationSettings",
  "app/etc/util",
  "dojo/json",
  "dojo/text!app/configs/AppConfig.json",
  "dojo/dom",
  "dojo/on"],
  function (declare, lang, array, domConstruct, topic, appTopics, template, i18n, SearchComponent,
    DropPane, QClause, TermsAggregationSettings, Util, JSON, appconfigs, dom, on) {

    var oThisClass = declare([SearchComponent], {

      i18n: i18n,
      templateString: template,

      allowSettings: null,
      field: null,
      label: null,
      open: false,
      sortByName: false,
      sortByAmount: false,
      viewLimit: 0,
      autoCloseWhenEmpty: false,
      props: null,

      _initialSettings: null,
      _entries: null,
      _entryNames: null,
      _entryOrders: null,
      _excludeTerm: '',

      AppConfig: JSON.parse(appconfigs),

      postCreate: function () {
        this.inherited(arguments);

        this._initialSettings = {
          label: this.label,
          field: this.field
        };
        if (this.props) {
          this._initialSettings.props = lang.clone(this.props);
        }

        if (this.allowSettings === null) {
          if (AppContext.appConfig.search && !!AppContext.appConfig.search.allowSettings) {
            this.allowSettings = true;
          }
        }
        if (this.allowSettings) {
          var link = this.dropPane.addSettingsLink();
          link.onclick = lang.hitch(this, function (e) {
            var d = new TermsAggregationSettings({
              targetWidget: this
            });
            d.showDialog();
          });
        }

        this._entries = new Map();

        const entryLang = (dojo.config.locale || 'en').replaceAll('-', '_');
        let valueList = [];
        switch (this.field) {
          case 'themes_s':
            // FSDT
            valueList = this.AppConfig.theme;
            break;
          case 'categories_s':
            // CSDI Category
            valueList = this.AppConfig.category;
            break;
          case 'contact_organizations_s':
            // Organization (Provider List)
            valueList = this.AppConfig.provider;
            break;
        }
        this._entryNames = new Map(valueList.map((obj) => [obj.en, obj[entryLang]]));
        if (valueList.length > 0 && 'order' in valueList[0]) {
          this._entryOrders = new Map(valueList.map((obj) => [obj.en, obj.order]));
        }

        if (this.props && typeof this.props.missing === "string") {
          this._excludeTerm = lang.trim(this.props.missing);
        }

        topic.subscribe(appTopics.SelectSearchFilterTerm, lang.hitch(this, function (params) {
          if (params.field !== this.field) {
            return;
          }
          if (this._entries.has(params.term)) {
            this.addQClause(params.term);
          } else if (!params.retryAfterClearAll) {
            topic.publish(appTopics.ClearAllSearchFilters, {});
            setTimeout(
              () => {
                topic.publish(
                  appTopics.SelectSearchFilterTerm,
                  Object.assign({}, params, { retryAfterClearAll: true })
                );
              },
              500
            );
          }
        }));

		this.getCatalogFilter();
      },

      postMixInProperties: function () {
        this.inherited(arguments);
        if (typeof this.label === "undefined" || this.label === null || this.label.length === 0) {
          this.label = this.field;
        }
      },

      getQClause: function (term, name) {
        const tip = i18n.search.appliedFilters.tipPattern
            .replaceAll('{type}', this.label)
            .replaceAll('{value}', name);

        const query = this._excludeTerm && term === this._excludeTerm ?
          { "bool": { "must_not": { "exists": { "field": this.field } } } } :
          { "term": { [this.field]: term } };

        return new QClause({
          label: name,
          tip,
          parentQComponent: this,
          removable: true,
          scorable: true,
          query,
        });
      },

      addQClause: function (term) {
        const name = this._entryNames.get(this.chkName(term));
        const qClause = this.getQClause(term, name);
        this.onClickPushQClause(qClause, true);
        topic.publish(appTopics.ShowSearchResultsView, {});
      },

      addEntry: function (term, count) {
        const name = this._entryNames.get(this.chkName(term));

        const nd = domConstruct.create('div', {
          className: `filter-content ${this.field}`,
          'data-name': name,
          'data-amount': count,
        }, this.entriesNode);

        domConstruct.create('button', {
          type: 'button',
          textContent: `${name} (${count})`,
          onclick: lang.hitch(this, function () {
            this.addQClause(term);
          })
        }, nd);
      },

      chkName: function (term) {
        var name = term;
        if (this.field === "sys_access_groups_s" && typeof name === "string" &&
          AppContext.geoportal.supportsGroupBasedAccess) {
          array.some(AppContext.appUser.getGroups(), function (group) {
            if (group.id === name) {
              name = group.name;
              return true;
            }
          });
        }
        return name;
      },

      hasField: function () {
        return (typeof this.field !== "undefined" && this.field !== null && this.field.length > 0);
      },

      /* SearchComponent API ============================================= */

      appendQueryParams: function (params) {
        if (!this.hasField()) return;
        this.appendQClauses(params);

        if (!params.aggregations) params.aggregations = {};
        var key = this.getAggregationKey();
        var props = { "field": this.field };
        if (typeof this.props !== "undefined" && this.props !== null) {
          delete this.props.field; // TODO ??
          lang.mixin(props, this.props);
        }
        params.aggregations[key] = { "terms": props };
      },

      processResults: function (searchResponse) {
        this._entries.clear();
        domConstruct.empty(this.entriesNode);
        var key = this.getAggregationKey();
        if (searchResponse.aggregations) {
          var data = searchResponse.aggregations[key];
          if (data && data.buckets) {
            const entries = data.buckets.filter(
              (entry) => this._entryNames.has(this.chkName(entry.key))
            );
            if (this._entryOrders) {
              entries.sort(
                (a, b) => this._entryOrders.get(a.key) - this._entryOrders.get(b.key)
              );
            }
            for (const entry of entries) {
              this._entries.set(entry.key, entry);
              this.addEntry(entry.key, entry.doc_count);
            }
          }
        }

        if (this.sortByName || this.sortByAmount) {
          this.dropPane.sort();
        }
        if (this.viewLimit > 0) {
          this.dropPane.viewMore(false);
        }
        if (this.autoCloseWhenEmpty) {
          this.dropPane.checkAutoClose();
        }
      },

		getCatalogFilter: function() {
			var v = "";
			var isFSDT = false;
			var temp = {};
			var tempObj = [];
			var provider = Util.getRequestParam("provider");
			var cat = Util.getRequestParam("cat");
			var key = Util.getRequestParam("key");
			var csdi_filter = sessionStorage['csdi-filter'];
			if (provider != null || cat != null || key != null) {
				if (provider != null) {
					v = provider;
					temp = { displayVal: v, field: 'contact_organizations_s', value: v };
					tempObj.push(temp);
				}
				if (cat != null) {
					v = cat;
					if (cat.indexOf("FSDT") > 0) isFSDT = true;
					if (isFSDT) temp = { displayVal: v, field: 'themes_s', value: v };
					else temp = { displayVal: v, field: 'categories_s', value: v };
					tempObj.push(temp);
				}
			}else if (csdi_filter) {
				if (JSON.parse(csdi_filter).length) tempObj = JSON.parse(csdi_filter);
				else tempObj.push(JSON.parse(csdi_filter));
			}
			
			if (tempObj.length > 0){
				for (var i=0;i<tempObj.length;i++){
					if (tempObj[i].field == this.field){
						const qClause = this.getQClause(tempObj[i].value, tempObj[i].displayVal);
						this.pushQClause(qClause, false);	
					}
				}
			}
		}
    });

    return oThisClass;
  });
