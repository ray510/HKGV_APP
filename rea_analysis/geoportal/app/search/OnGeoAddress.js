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
        "dojo/dom-class",
        "dojo/request",
        "dojo/topic",
        "app/context/app-topics",
        "dojo/text!./templates/OnGeoAddress.html",
        "dojo/i18n!app/nls/resources",
        "app/search/SearchComponent",
        "app/search/DropPane",
        "app/search/QClause",
        "dojo/dom",
        "dojo/on",
        "app/search/CollectionsFilterSettings",
        "dijit/registry",
        "dojo/request",
        "dojox/xml/DomParser",
        "app/search/SpatialFilter"
    ],
    function(declare, lang, array, domConstruct, domClass, dojoRequest, topic, appTopics, template, i18n, SearchComponent,
             DropPane, QClause, dom,on,CollectionsFilterSettings,registry,dojoRequest,DomParser,SpatialFilter) {

        var oThisClass = declare([SearchComponent], {

            i18n: i18n,
            templateString: template,

            allowSettings: null,
            field: null,
            label: null,
            open: false,
            props: null,

            _initialSettings: null,
            links: [],
            selectedCollectionName: "",

            postCreate: function() {
                this.inherited(arguments);

                this._initialSettings = {
                    label: this.label
                };
                if (this.props) {
                    this._initialSettings.props = lang.clone(this.props);
                }

                if (this.allowSettings === null) { //设置按钮
                    if (AppContext.appConfig.search && !!AppContext.appConfig.search.allowSettings) {
                        this.allowSettings = true;

                    }
                }
                if (this.allowSettings) {//设置弹窗

                    var link = this.dropPane.addSettingsLink();
                    link.onclick = lang.hitch(this,function(e) {
                        var d = new CollectionsFilterSettings({
                            targetWidget: this
                        });
                        d.showDialog();
                    });
                }



            },
            startup:function (){
                var serButton=dom.byId("searchAdd");
                var serText=document.getElementById("searchText");
                var lat,lon;
                // var serText=registry.byId("searchText")
                //搜索按钮事件
                this.own(on(serButton,"click",lang.hitch(this,function (e) {
                    var str=serText.value;
                    var url ="https://www.als.ogcio.gov.hk/galookup?ga="+str;

                    var xml = dojoRequest.get(url, {headers: {
                            "X-Requested-With": null,
                            "Access-Control-Allow-Origin": null
                            // Accept:"application/json"
                        }}).then(function (request){
                            //处理返回值，解析经纬度
                        //console.log(request)

                        var xmlDom= DomParser.parse(request);

                        //console.log(xmlDom);
                        lat=xmlDom.getElementsByTagName("Latitude")[0].childNodes[0].nodeValue;
                        //console.log(lat);
                        lon=xmlDom.getElementsByTagName("Longitude")[0].childNodes[0].nodeValue;
                        //console.log(lon);

                        // SpatialFilter._testLatLog();
                        topic.publish(appTopics.OnGeoAddress,{Lat:lat,Lon:lon});
                    });


                })));
            },

            postMixInProperties: function() {

            },

            addEntry: function(term,count,missingVal) {

            },

            chkName: function(term){

            },

            hasField: function() {
            },

            /* SearchComponent API ============================================= */
            whenQClauseRemoved: function(qClause) {
            },

            appendQueryParams: function(params) {

            },

            processResults: function(searchResponse) {





            },

            highlight: function(collectionName) {

            }

        });

        return oThisClass;
    });
