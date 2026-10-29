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
        "dojo/_base/array",
        "dojo/query",
        "dojo/topic",
        "app/context/app-topics",
        "dojo/text!./templates/ResultsPane.html",
        "dojo/i18n!app/nls/resources",
        "app/search/SearchComponent",
        "app/search/ItemCard",
        "app/search/Paging",
        "dojox/widget/Standby",
        "app/etc/util"],
    function (declare, array, query, topic, appTopics, template, i18n, SearchComponent, ItemCard, Paging, Standby, Util) {

        var oThisClass = declare([SearchComponent], {

            i18n: i18n,
            templateString: template,

            label: i18n.search.results.label,
            open: true,
            paging: null,
            sortField: null,
            sortDir: null,

            postCreate: function () {
                this.inherited(arguments);
                this.paging = new Paging({});
                this.paging.placeAt(this.resultsFooterNode);
				// set default sorting field
				this.sortField = 'apiso_Modified_dt';
				this.sortDir = 'desc';
                /*
                // no longer needed
                this.own(aspect.after(this.paging,"search",lang.hitch(this,function(){
                  this.search();
                })));
                */
				var self = this;
				topic.subscribe(appTopics.SortByField, function(sort) {
					if (self._started) {
						var text;
						switch (sort) {
							case 'sort-by-publication-date':
								text = i18n.search.sort.publicationDateDesc;
								self.sortField = 'apiso_PublicationDate_dt';
								self.sortDir = 'desc';
								break;
							case 'sort-by-metadata-date':
								text = i18n.search.sort.metadataDateDesc;
								self.sortField = 'apiso_Modified_dt';
								self.sortDir = 'desc';
								break;
							case 'sort-by-title-asc':
								text = i18n.search.sort.titleAsc;
								if (localStorage['csdi-lang'] == 'zh-hk') self.sortField = 'title_tc_s';
								else if (localStorage['csdi-lang'] == 'zh-cn') self.sortField = 'title_sc_s';
								else self.sortField = 'title.sort';
								self.sortDir = 'asc';
								break;
							case 'sort-by-title-desc':
								text = i18n.search.sort.titleDesc;
								if (localStorage['csdi-lang'] == 'zh-hk') self.sortField = 'title_tc_s';
								else if (localStorage['csdi-lang'] == 'zh-cn') self.sortField = 'title_sc_s';
								else self.sortField = 'title.sort';
								self.sortDir = 'desc';
								break;
							case 'sort-by-relevance':
								text = i18n.search.sort.relevance;
								self.sortField = null;
								self.sortDir = null;
								break;
						}
						self.sortLabel.innerHTML = text;
						$('#sort-by-dropdown-menu button').each(function() {
							this.querySelector('i').hidden = (this.querySelector('span').textContent != text);
						});
					}
				});
                document.body.appendChild(this.statusNode.domNode);
                this.statusNode.target = this.containerNode;
            },

            destroyItems: function (searchContext, searchResponse) {
                this.noMatchNode.style.display = "none";
                this.noMatchNode.innerHTML = "";
                var rm = [];
                array.forEach(query(".g-item-card", this.itemsNode), function (child) {
                    //if (child.isItemCard)
                    rm.push(child);
                });
                array.forEach(rm, function (child) {
                    this.itemsNode.removeChild(child);
                }, this);
            },

            showNoMatch: function () {
                this.setNodeText(this.noMatchNode, i18n.search.results.noMatch);
                this.noMatchNode.style.display = "block";
            },

            /* SearchComponent API ============================================= */

            appendQueryParams: function (params) {
                this.paging.appendQueryParams(params);
                if (Util.getRequestParam("sort") && Util.getRequestParam("sort").split(":").length==2) {
                  this.sortField = Util.getRequestParam("sort").split(":")[0];
                  this.sortDir = Util.getRequestParam("sort").split(":")[1];
                }
                if (this.sortField !== null && this.sortDir !== null) {
                    params.urlParams.sort = this.sortField + ":" + this.sortDir;
                }
                this.statusNode.show();
            },

            processError: function (searchError) {
                this.statusNode.hide();
                this.destroyItems();
                this.setNodeText(this.noMatchNode, i18n.search.results.error);
                this.noMatchNode.style.display = "block";

            },

            processResults: function (searchResponse) {
                this.statusNode.hide();
                this.paging.searchPane = this.searchPane;
                this.paging.processResults(searchResponse);
                this.destroyItems();
                if (searchResponse.hits) {
                    var searchHits = searchResponse.hits;
                    var hits = searchHits.hits;
                    var total = searchHits.total;
                    var num = hits.length;
                    var itemsNode = this.itemsNode;
                    array.forEach(hits, function (hit) {
                        var itemCard = new ItemCard({
                            itemsNode: this.itemsNode,
                            searchPane: this.searchPane
                        });
                        itemCard.render(hit);
                        //console.log(itemsNode);
                        itemCard.placeAt(itemsNode);
                    }, this);
                }
            },

            /*
            setSortDir: function (dir) {
                if (dir === null) {
                    this.sortDir = null;
                    this.sortOrderBtn.hidden = true;
                    return;
                }

                if (!dir) {
                    dir = this.sortDir === 'asc' ? 'desc' : 'asc';
                }

                this.sortDir = dir;

                this.sortOrderBtn.classList.toggle('desc', dir === 'desc');
                this.sortOrderBtn.hidden = false;
            },
            */

            sortByRelevance: function () {
				this.sortByField('sort-by-relevance');
                this.search();
            },

            sortByTitleAsc: function () {
				this.sortByField('sort-by-title-asc');
                this.search();
            },

            sortByTitleDesc: function () {
				this.sortByField('sort-by-title-desc');
                this.search();
            },
			
			sortByPublicationDateDesc: function () {
				this.sortByField('sort-by-publication-date');
                this.search();
            },

			sortByMetadataDateDesc: function () {
				this.sortByField('sort-by-metadata-date');
			    this.search();
			},

            /*
            toggleSortOrder: function () {
                this.setSortDir();
                this.search();
            },
            */

            showFilter: function () {
                topic.publish(appTopics.ShowSearchFiltersView, {});
            },
			
			sortByField: function (sort) {
				topic.publish(appTopics.SortByField, sort);
			}
        });

        return oThisClass;
    });
