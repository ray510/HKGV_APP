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
	"dojo/query",
	"dojo/dom-class",
	"dojo/topic",
	"dojo/io-query",
	"app/context/app-topics",
	"dijit/registry",
	"dijit/_WidgetBase",
	"dijit/_TemplatedMixin",
	"dijit/_WidgetsInTemplateMixin",
	"dojo/text!./templates/MetadataInfoPane.html",
	"dojo/i18n!app/nls/resources",
	"dojo/request",
	"app/context/AppClient",
	"app/search/ItemHtml",
	"dojo/router",
	"dojo/dom-construct"
],
	function(declare, lang, array, query, domClass, topic, ioQuery, appTopics, registry,
		_WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin, template, i18n,
		dojoRequest, AppClient, ItemHtml, router, domConstruct) {

		var oThisClass = declare([_WidgetBase, _TemplatedMixin, _WidgetsInTemplateMixin], {

			i18n: i18n,
			templateString: template,
			checkUrl: true,
			item: null,

			constructor: function(args) {
		      lang.mixin(this,args);
		    },

			postCreate: function() {
				this.inherited(arguments);
			},

			startup: function() {
				this.inherited(arguments);

				var windowsUri = window.location.href;
				if (this.checkUrl && window.location.hash == '#metadataInfoPanel' && windowsUri.indexOf("?") === -1) {
					var selectedItem = sessionStorage.getItem('selectedItem');
//					if (selectedItem != null && windowsUri.indexOf("?") === -1) {
					if (selectedItem != null && selectedItem!="") {
						var uriBegin = windowsUri.substring(0, windowsUri.indexOf('#'));
						uriBegin = uriBegin.substring(0, uriBegin.indexOf('?'));
						
						var uriEnd = windowsUri.substring(windowsUri.indexOf('#'));
						var actualUri = uriBegin + '?' + selectedItem + uriEnd;
						//console.log('Actual URI: ', actualUri);
						windowsUri = actualUri;
					}
				}
				if (this.checkUrl && window.location.hash == '#metadataInfoPanel' && windowsUri.indexOf("?") !== -1) {
					var s = windowsUri.substring(windowsUri.indexOf("?") + 1, windowsUri.length);
					var hash = s.indexOf("#") >= 0 ? s.substring(s.indexOf("#") + 1, s.length) : "";
					s = s.indexOf("#") >= 0 ? s.substring(0, s.indexOf("#")) : s;

					var o = ioQuery.queryToObject(s);

					var datasetId = "";
					if (o && typeof o.datasetId === "string") {
						//console.log("datasetId found: " + o.datasetId);
						datasetId = o.datasetId;
					}
					else if(sessionStorage['selectedItem']!=null){
						datasetId = sessionStorage['selectedItem'].split("=")[1];
					}
					
					if(datasetId!=""){
						var uri = "./rest/metadata/item/" + datasetId;
						var csdiToken = sessionStorage['csdi-geoportal-token'];
						if(typeof csdiToken !== "undefined" && csdiToken!=null && csdiToken!=""){
							var tokenJson = JSON.parse(csdiToken);
							if(typeof tokenJson.access_token !== "undefined" && tokenJson.access_token!=null && tokenJson.access_token!=""){
								uri = uri + "?access_token=" + tokenJson.access_token;
							}
						}
						
						var item = null;
						$.ajax({
							type: "GET",
							url: uri,
					        async: false,
							success : function(result) {
								item = result;
								this.item = item;
								
								if(typeof item !== "undefined" && item!=null){
									sessionStorage.setItem('selectedItem', 'datasetId=' + item._id);
								}
								else {
									sessionStorage.removeItem('selectedItem');
								}
							},
							error: function(xhr, statusText, err){
								//console.log("Error:" + err);
								sessionStorage.removeItem('selectedItem');
					        }
						});
						
						if(typeof item !== "undefined" && item!=null){
							this.showData(item, uri);
						}
						else{
							$("#idCatalogTitle").click();
						}
					}else{
						$("#idCatalogTitle").click();	
					}
				}else if (this.checkUrl && window.location.hash == '#metadataInfoPanel') {
					$("#idCatalogTitle").click();
				}
				
				if (location.hash == '#metadataInfoPanel')
					history.replaceState(location.pathname, document.title, location.pathname.replace(/\/+$/g, "") + "/#metadataInfoPanel");
			},

			showData: function(item, uri) {

				if(typeof AppContext.itemHtmlObj !== "undefined" && AppContext.itemHtmlObj!=null){
					AppContext.itemHtmlObj.destroy();
					AppContext.itemHtmlObj = null;
					
					$(".g-metadata-info").html("<div id=\"g-metadata-info-item\"></div>");
				}
				var itemTitle = item.title;
				if (typeof itemTitle == "undefined" || itemTitle == "N/A")
					itemTitle = item._source.apiso_Title_txt;
				var itemHtml = new ItemHtml({
					//title: itemTitle,
					title: "",
					uri: uri
				}, dojo.byId("g-metadata-info-item"));
				itemHtml.startup();
				
				itemHtml.render(item);
				itemHtml._starter();
				
				AppContext.itemHtmlObj = itemHtml;
			},

			showDataFromClick: function(item, uri) {
				var item = null;
				$.ajax({
					type: "GET",
					url: uri,
					async: false,
					success : function(result) {
						item = result;
						this.item = item;

						if(typeof item !== "undefined" && item!=null){
							sessionStorage.setItem('selectedItem', 'datasetId=' + item._id);
						}
						else {
							sessionStorage.removeItem('selectedItem');
						}
					},
					error: function(xhr, statusText, err){
						//console.log("Error:" + err);
						sessionStorage.removeItem('selectedItem');
					}
				});

				if(typeof item !== "undefined" && item!=null){
					this.showData(item, uri);
				}
				else{
					$("#idCatalogTitle").click();
				}			}
			
		});

		return oThisClass;
	});
