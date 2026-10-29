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
define(["dojo/_base/lang", 
        "dojo/i18n!app/nls/resources", 
        "dojo/dom-style",
		"dojo/on",
		"dojo/dom",
		"dojo/router"],
function (lang, i18n, domStyle, on, dom, router) {
  
  var oThisObject = {

    checkMixedContent: function(uri) {
      if ((typeof window.location.href === "string") && (window.location.href.indexOf("https://") === 0)) {
        if ((typeof uri === "string") && (uri.indexOf("http://") === 0)) {
          uri = "https:"+uri.substring("5");
        }
      }
      return uri;
    },
    
    escapeForLucene: function(value) {
      var a = ['+', '-', '&', '!', '(', ')', '{', '}', '[', ']', '^', '"', '~', '*', '?', ':', '\\'];
      var r = new RegExp("(\\" + a.join("|\\") + ")", "g");
      return value.replace(r, "\\$1");
    },
    
    setNodeText: function(nd,text) {
      nd.innerHTML = "";
      if (text) nd.appendChild(document.createTextNode(text));
    },
    
    getRequestParam: function(name) {
      param = location.search.split(/[?&]/).filter(function(p){ return p.startsWith(name); });
      if (param && param.length>0) {
        var value = param[0].substring(name.length+1);
        return decodeURIComponent(value);
      }
      return null;
    },

	outputMessageFromI18n: function(key){
		var strArr = key.split('.');
		var resultLangRes;
		for(j=0; j<strArr.length; j++){
			if(j==0){
				resultLangRes = i18n[strArr[j]];
				
				if(resultLangRes==null || resultLangRes==""){
					return key;
				}
			}
			else{
				resultLangRes = resultLangRes[strArr[j]];
			}
		}
		
		return resultLangRes;
	},
	
	setHKDateFmt: function(dateValue) {
		var yearPattern = /^[0-9]{4}$/g;
		var yearMonthPattern = /^[0-9]{4}-[0-9]{1,2}$/g;
		if(yearPattern.test(dateValue))
			return dateValue;
		else if(yearMonthPattern.test(dateValue)){
			var fmtdate = new Date(dateValue);
      		return fmtdate.format('m/Y');
		}
		else {
			var fmtdate = new Date(dateValue);
      		return fmtdate.format('d/m/Y');
		}
    },

    randomArray: function(arraySize) {
	 var array = new Array(arraySize);

     for (var i=0;i<array.length;i++) array[i] = i;

//     for (var i = array.length - 1; i > 0; i--) {
//        var j = Math.floor(Math.random() * (i + 1));
//        var temp = array[i];
//        array[i] = array[j];
//        array[j] = temp;
//     }
     return array;
    },

	activeMetatdataInfoMenu: function(){
		//domStyle.set("idMetadataInfoTitle", "visibility", "visible");
/*		var metID = document.getElementById("idMetadataInfoTitle");

        if (metID != null) {
	      metID.style.visibility = 'visible';
        }
		$('#idMenuTitle').removeClass('active');
		$('#idCatalogTitle').removeClass('active');
		$('#idMapTitle').removeClass('active');
		$('#idMetadataInfoTitle').addClass('active');
*/		
		show_footer();
	},
	
	findXmlValueByLocale: function(xmlNode){
		try{
			if(typeof xmlNode === "undefined"){
				return "";
			}
			if(xmlNode.getElementsByTagName("gmd:LocalisedCharacterString").length > 0){
				var enValue = "";
				var zhValue = "";
				
				for(var i=0; i<xmlNode.getElementsByTagName("gmd:LocalisedCharacterString").length; i++){
					var localeNode = xmlNode.getElementsByTagName("gmd:LocalisedCharacterString")[i];
					////console.log("locale: " + localeNode.attributes[0].nodeValue +", nodeValue: "+localeNode.childNodes[0].nodeValue);
					
					if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == "#EN" 
							&& localeNode.childNodes.length>0 && localeNode.childNodes[0].nodeValue!=""){
						enValue = localeNode.childNodes[0].nodeValue;
					}
					else if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == "#ZH" 
							&& localeNode.childNodes.length>0 && localeNode.childNodes[0].nodeValue!=""){
						zhValue = localeNode.childNodes[0].nodeValue;
					}
					
					if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == i18n.lang){
						if(localeNode.childNodes.length > 0){
							var nodeval = localeNode.childNodes[0].nodeValue;
							
							if(nodeval.trim()!="")
								return nodeval;
						}
							
					}
				}
				
				if(i18n.lang=="#CN" && zhValue.trim()!=""){
					return zhValue;
				}
				if(enValue.trim() !== "") {
					return enValue;
				}
				
				//console.log("no locale string found, return CharacterString");
				return xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes[0].nodeValue;
			}
			else if(xmlNode.getElementsByTagName("gco:CharacterString").length > 0 && 
				typeof xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes !== "undefined" && xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes.length > 0){
				return xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes[0].nodeValue;
			}
			else{
				return "";
			}
		}
		catch(ex){
			return "";
		}
	},
	
	/*
	findXmlValueByCharacterString: function(xmlNode){
		try{
			if(typeof xmlNode === "undefined"){
				return "";
			}
			if(xmlNode.getElementsByTagName("gco:CharacterString").length > 0 && 
				typeof xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes !== "undefined" && xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes.length > 0){
				return xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes[0].nodeValue;
			}
			else{
				return "";
			}
		}
		catch(ex){
			return "";
		}
	},
	*/

	  findXmlTitleValueByLocale: function(xmlNode, locale){
		  try{
			  if(typeof xmlNode === "undefined"){
				  return "";
			  }
			  if(xmlNode.getElementsByTagName("gmd:LocalisedCharacterString").length > 0){
				  var enValue = "";
				  var zhValue = "";

				  for(var i=0; i<xmlNode.getElementsByTagName("gmd:LocalisedCharacterString").length; i++){
					  var localeNode = xmlNode.getElementsByTagName("gmd:LocalisedCharacterString")[i];
					  ////console.log("locale: " + localeNode.attributes[0].nodeValue +", nodeValue: "+localeNode.childNodes[0].nodeValue);

					  if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == "#EN"
						  && localeNode.childNodes.length>0 && localeNode.childNodes[0].nodeValue!=""){
						  enValue = localeNode.childNodes[0].nodeValue;
					  }
					  else if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == "#ZH"
						  && localeNode.childNodes.length>0 && localeNode.childNodes[0].nodeValue!=""){
						  zhValue = localeNode.childNodes[0].nodeValue;
					  }

					  if(localeNode.attributes.length>0 && localeNode.attributes[0].nodeValue == "#"+locale){
						  if(localeNode.childNodes.length > 0){
							  var nodeval = localeNode.childNodes[0].nodeValue;

							  if(nodeval.trim()!="")
								  return nodeval;
						  }

					  }
				  }

				  if(locale=="CN" && zhValue.trim()!=""){
					  return zhValue;
				  }
				  if(locale=="EN" && enValue.trim() !== "") {
					  return enValue;
				  }

				  //console.log("no locale string found, return CharacterString");
				  return xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes[0].nodeValue;
			  }
			  else if(xmlNode.getElementsByTagName("gco:CharacterString").length > 0 &&
				  typeof xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes !== "undefined" && xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes.length > 0){
				  return xmlNode.getElementsByTagName("gco:CharacterString")[0].childNodes[0].nodeValue;
			  }
			  else{
				  return "";
			  }
		  }
		  catch(ex){
			  return "";
		  }
	  },

	update_header: function(navName) {
      // Load CSDI Header
      var csdi_lang = localStorage["csdi-lang"] != null ? localStorage["csdi-lang"] : "en";
      $.ajax({
			url: set_csdi_url('info/getHeader'),
            type: "GET",
            data: { site: 'geo', nav: navName, lang: csdi_lang},
            async: false,
            success: function (result) {
            	$('#csdi-nav-header').html(result);
				var title;
				if (csdi_lang == 'zh-hk')
					title = '空間數據共享平台入門網站' + (document.getElementById("idCSDI_Site").innerHTML == 'OPEN' ? '' : ' (政府內部使用)');
				else if (csdi_lang == 'zh-cn')
					title = '空间数据共享平台入门网站' + (document.getElementById("idCSDI_Site").innerHTML == 'OPEN' ? '' : ' (政府内部使用)');
				else
					title = 'Common Spatial Data Infrastructure (CSDI) Portal' + (document.getElementById("idCSDI_Site").innerHTML == 'OPEN' ? '' : ' for Government');
				$('#idPageTitle').text(title);
        	}
      });

	 // Load CSDI Notification
	 $.ajax({
			url: set_csdi_url('getNotification'),
            type: "GET",
            async: false,
            success: function (result) {
            	$('#site-notification').html(result); 
        	}
      });

     // Save Session ID
	 var curSID = localStorage["csdi-sid"]; 
	 var sessionID = dom.byId("idCSDIUser").innerText;
     if (sessionID != null && location.protocol == 'http:') {
	  if (curSID == null || sessionID != curSID) window.localStorage.setItem('csdi-sid',sessionID);
     }

     // Menu Navigation Indicator
     on(dom.byId("idCatalogTitle"), "click", lang.hitch(this, function(e) {
		this.switchPanel('searchPanel');
		show_footer();
		close_top_nav();
		router.go("searchPanel");
     }));

     on(dom.byId("idMapTitle"), "click", lang.hitch(this, function(e) {
		this.switchPanel('mapPanel');
		hide_footer();
		close_top_nav();
		sessionStorage.setItem('fr', 'catalog');
		if (sessionStorage.getItem("currentmap") == "3dmap") {
			router.go("3dmapInfoPanel");
		}
		else router.go("mapPanel");
      	
     }));
	 
	 on(dom.byId("idMapTitleJs4"), "click", lang.hitch(this, function(e) {
			this.switchPanel('mapPanelJs4');
	 		hide_footer();
			close_top_nav();
	 		sessionStorage.setItem('fr', 'catalog');
	 		if (sessionStorage.getItem("currentmap") == "3dmap") {
	 			router.go("3dmapInfoPanel");
	 		}
	 		else {
				router.go("mapPanelJs4");
				
				//Call the iframe to add layer (if any)
				$("#iMapPanelJs4")[0].contentWindow.postMessage({
					action: "addLayer",
					source: "tab",
					args: [""]
				});
			}
	       	
	      }));
		
    },
	
	switchPanel: function (panel_id) {
		var panels = ['searchPanel', 'metadataInfoPanel', 'mapPanel', 'mapPanelJs4', '3dmapInfoPanel'];
		panels.forEach(id => {
			if (id !== panel_id) {
				$('#' + id).removeClass('active in show');
			} else {
				$('#' + id).addClass('active in show');
				
				if (id == 'searchPanel') {
					$('.site-nav__catalog a').addClass('active');
					$('.site-nav__map a').removeClass('active');
				} else if (id == 'mapPanel' || id == 'mapPanelJs4') {
					$('.site-nav__catalog a').removeClass('active');
					$('.site-nav__map a').addClass('active');
				} else {
					$('.site-nav__catalog a').removeClass('active');
					$('.site-nav__map a').removeClass('active');
				}
			}
		});
	},

	addViewLog: function(itemId, processTime, type){
		if(typeof itemId !== "undefined") {
			$.ajax({
				type: "POST",
				url: "/csdi-webpage/addViewLog",
				dataType : 'json',
				data: {"datId":itemId, "processTime":parseInt(processTime), "type":type},
				contentType: "application/x-www-form-urlencoded; charset=utf-8",
		        async: true,
				success : function(result) {
					//console.log(result);
				},
				error: function(xhr, statusText, err){
					//console.log("Error:" + err);
		        }
			});
		}
		this.sysUserActivityLog("Data Catalogue","View Log",itemId);
	},
	sysUserActivityLog: function(eventType,action,srvName){
				var data = {
					'eventType': eventType,
					'action': action,
					'section': srvName
				};
				$.ajax({
					type: 'POST',
					url : '/csdi-webpage/endUserActivityLog',
					data:  data,
					dataType: 'json',
			        async: false,
					success : function(result) {				
						if(result.respHeader.retCode=="1"){
		
							//console.log("success");
						}
						else if(result.errorDetail!=null){
							//console.log("fail");
						}
						else{
							showErrorAlert('Connect to CSDI Portal failed');
						}
					},
					error: function(xhr, statusText, err){
						//console.log("Error:" + err);
						//alert('Error');
			        }
				});						
	},	topFunction: function(){
		$('div#app.g-app').animate({
			scrollTop: 0  // Scroll to top          
		}, 0);		
	},  LsLoad: function (_url){
		  var f;
		  $.ajax({
			  type: "GET",
			  async:false,
			  cache: false,
			  url: _url,
			  data: "",
			  success: function() {
				  f = true;
				  return ;
			  },
			  error: function() {
				  f = false;
				  return ;
			  }
		  });
		  return f;
	  },
	  
	  updateUrlByAccess: function(link, accessType, isTa) {
		  if (!accessType.includes('po') && !accessType.includes('restrict') && !isTa) {
			  link = this.updateUrlByEnv(link);
		  }
		  return link;
	  },

	  updateUrlByEnv: function(link){
			if (!link) return link;
	  		if(AppContext.appConfig.environment.setting=="GNET"){
	  			link = link.replace(AppContext.appConfig.openDomain, AppContext.appConfig.gnetDomain);
	  			
	  			if(AppContext.appConfig.gnetStaticDomain!=null && link.indexOf("/restrict/") < 0 && link.indexOf("/govt-trial/") < 0) {
	  				link = link.replace(AppContext.appConfig.gnetDomain+"/csdi-webpage/download/", AppContext.appConfig.gnetStaticDomain+"/csdi-webpage/download/");
	  				link = link.replace(AppContext.appConfig.gnetDomain+"/csdi-webpage/view/", AppContext.appConfig.gnetStaticDomain+"/csdi-webpage/view/");
	  				
	  				link = link.replace(AppContext.appConfig.gnetDomain+"//csdi-webpage/download/", AppContext.appConfig.gnetStaticDomain+"/csdi-webpage/download/");
	  				link = link.replace(AppContext.appConfig.gnetDomain+"//csdi-webpage/view/", AppContext.appConfig.gnetStaticDomain+"/csdi-webpage/view/");
	  			}
	  			
	  			link = link.replace(AppContext.appConfig.openApiDomain, AppContext.appConfig.gnetApiDomain);
	  		}
	  		else{
	  			link = link.replace(AppContext.appConfig.gnetDomain, AppContext.appConfig.openDomain);
	  			
	  			if(AppContext.appConfig.openStaticDomain!=null && link.indexOf("/po/")<0) {
	  				link = link.replace(AppContext.appConfig.openDomain+"/csdi-webpage/download/", AppContext.appConfig.openStaticDomain+"/csdi-webpage/download/");
	  				link = link.replace(AppContext.appConfig.openDomain+"/csdi-webpage/view/", AppContext.appConfig.openStaticDomain+"/csdi-webpage/view/");
	  				
	  				link = link.replace(AppContext.appConfig.openDomain+"//csdi-webpage/download/", AppContext.appConfig.openStaticDomain+"/csdi-webpage/download/");
	  				link = link.replace(AppContext.appConfig.openDomain+"//csdi-webpage/view/", AppContext.appConfig.openStaticDomain+"/csdi-webpage/view/");
	  			}
	  			
	  			link = link.replace(AppContext.appConfig.gnetApiDomain, AppContext.appConfig.openApiDomain);
	  		}
	  		
	  		return link;
	  	},

	children: function (node) {
		if (!node || !node.childNodes) {
			return [];
		}
		if (node.children) {
			return Array.from(node.children);
		}
		return Array.from(node.childNodes).filter((n) => n.nodeType === 1); // Node.ELEMENT_NODE
	},

	textContent: function (node) {
		let result = null;

		if (!node) {
			return result;
		}

		if ('textContent' in node) {
			return node.textContent;
		}

		switch (node.nodeType) {
		case 1: // Node.ELEMENT_NODE
		case 11: // Node.DOCUMENT_FRAGMENT_NODE
			result = Array.from(node.childNodes)
				.filter((n) => n.nodeType !== 7 && n.nodeType !== 8) // exclude processing instructions and comments
				.map((n) => this.textContent(n))
				.join('');
			break;

		case 2: // Node.ATTRIBUTE_NODE
			result = node.value;
			break;

		case 3: // Node.TEXT_NODE
		case 4: // Node.CDATA_SECTION_NODE
		case 7: // Node.PROCESSING_INSTRUCTION_NODE
		case 8: // Node.COMMENT_NODE
			result = node.nodeValue;
			break;

		case 9: // Node.DOCUMENT_NODE
		case 10: // Node.DOCUMENT_TYPE_NODE
			break;
		}

		return result;
	},

	getChildText: function (element, tag) {
		return this.textContent(
			this.children(element).find((el) => el.nodeName === tag)
		) ?? '';
	},

	gcoCharacterString: function (element) {
		return this.getChildText(element, 'gco:CharacterString');
	},

	gmdLocalisedCharacterString: function (element, locale) {
		if (!element) {
			return '';
		}

		if (!locale) {
			return this.gcoCharacterString(element);
		}

		const normalizedLocale = locale.startsWith('#') ? locale : '#' + locale.toUpperCase();

		const ptFreeText = this.children(element).find((el) => el.nodeName === 'gmd:PT_FreeText');

		if (!ptFreeText) {
			return this.gcoCharacterString(element);
		}

		const textGroups = this.children(ptFreeText).filter((el) => el.nodeName === 'gmd:textGroup');

		for (const textGroup of textGroups) {
			const localised = this.children(textGroup).find(
				(el) =>
					el.nodeName === 'gmd:LocalisedCharacterString' &&
					el.getAttribute('locale') === normalizedLocale
			);

			if (localised) {
				return this.textContent(localised);
			}
		}

		return this.gcoCharacterString(element);
	},

	gmdURL: function (element) {
		return this.getChildText(element, 'gmd:URL');
	},

	// note that this returns a document fragment
	cloneTemplate: function (templateNode) {
		return templateNode.ownerDocument.importNode(templateNode.content, true);
	},

	getSpriteIcon: function (refNode, name, classNames) {
		const svgNS = 'http://www.w3.org/2000/svg';
		const doc = refNode.ownerDocument;

		const icon = doc.createElement('span');
		icon.ariaHidden = true;
		icon.className = `${classNames || ''} sprite-icons sprite-icons--${name}`;

		const svg = doc.createElementNS(svgNS, 'svg');

		const use = doc.createElementNS(svgNS, 'use');
		use.setAttributeNS(null, 'href', `./custom/2024-revamp/images/sprite-icons.svg#${name}`);

		svg.appendChild(use);
		icon.appendChild(svg);

		return icon;
	},

	appendSpriteIcon: function (element, name, classNames) {
		const icon = this.getSpriteIcon(element, name, classNames);
		element.append(icon);
	},

	isHidden: function (element) {
		const win = element?.ownerDocument?.defaultView;
		let hidden = false;

		if (!win) {
			return hidden;
		}

		while (element) {
			if (win.getComputedStyle(element).getPropertyValue('display') === 'none') {
				hidden = true;
				break;
			}
			element = element.parentElement;
		}

		return hidden;
	},

	scrollIntoViewIfNeeded: function (element) {
		const rect = element.getBoundingClientRect();
		const windowHeight = element.ownerDocument.documentElement.clientHeight;
		let alignToTop = null;

		if (rect.top < 0) {
			alignToTop = true;
		} else if (rect.bottom > windowHeight) {
			alignToTop = rect.height >= windowHeight;
		}

		if (alignToTop !== null) {
			element.scrollIntoView(alignToTop);
		}
	},

	getESQuery: function (v) {
		let esQuery = {"bool": { 
            "must": [], "must_not": []
        } };
		// Operator Detection
		// ==========================================
		const isWildcardSearch = v.includes('*');
		const isExactMatch = v.includes('"');
		const isAndMatch = v.includes('&'); // NEW: Detect the '&' operator

		let positiveTerms = [];
		let negatedTerms = [];

		// Parse Negation (-): Only terms starting with ' -' are treated as exclusion
		const parts = v.trim().split(/\s+/);
		parts.forEach(part => {
		    if (part.startsWith('-') && part.length > 1) {
		        negatedTerms.push(part.substring(1)); // Get the term after '-'
		    } else {
		        positiveTerms.push(part);
		    }
		});

		const cleanSearchTerm = positiveTerms.join(' ').replace(/["&*]/g, '').trim();
		const cleanNegatedTerm = negatedTerms.join(' ').replace(/["&*]/g, '').trim();

		// ==========================================
		// Step 3: Elasticsearch Query Structure
		// ==========================================

		const searchFields = [
		    "apiso_Title_txt^10", 
		    "keywords_txt^2", 
		    "apiso_Abstract_txt",
		    "apiso_OrganizationName_txt", 
		    "apiso_Subject_txt",
			"apiso_Lineage_txt"
		];

		// --- Positive Match Logic ---
		if (isWildcardSearch) {
		    // Mode A: Wildcard Full Text Search
		    esQuery.bool.must.push({
		        "query_string": {
		            "query": `${cleanSearchTerm} *${cleanSearchTerm}*`,
		            "analyze_wildcard": true,
		            "fields": ["*",
		                        "apiso_Title_txt^10", 
		                        "keywords_txt^2"]
		        }
		    });
		} else if (isExactMatch) {
		    // Mode B: Exact Phrase Match
		    esQuery.bool.must.push({
				"query_string": {
					"query": `"${cleanSearchTerm}"`,
					"fields": searchFields
				}
		    });
		} else {
			// Mode C: Default AND / OR Fuzzy Match
			const operator = isAndMatch ? "and" : "or";
			esQuery.bool.must.push({
				"query_string": {
					"query": cleanSearchTerm,
					"fields": searchFields,
					"default_operator": operator.toUpperCase(),
					"fuzziness": "AUTO",
				}
			});
		}

		// --- Negation Logic (Exclude Terms) ---
		if (cleanNegatedTerm) {
		    esQuery.bool.must_not.push({
				"query_string": {
					"query": cleanNegatedTerm,
					"fields": ["*"]
				}
		    });
		}

		if (esQuery) return esQuery;
	},
	
	parseISO8601Duration: function (duration) {
		const regex = /P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/;
		const matches = duration.match(regex);

		if (!matches) {
			return null;
		}

		const years = parseInt(matches[1]) || 0;
		const months = parseInt(matches[2]) || 0;
		const days = parseInt(matches[3]) || 0;
		const hours = parseInt(matches[4]) || 0;
		const minutes = parseInt(matches[5]) || 0;
		const seconds = parseInt(matches[6]) || 0;

		const parts = [];

		if (years > 0) parts.push(this.getPluralSuffix(years, i18n.item.details.duration.year));
		if (months > 0) parts.push(this.getPluralSuffix(months, i18n.item.details.duration.month));
		if (days > 0) parts.push(this.getPluralSuffix(days, i18n.item.details.duration.day));
		if (hours > 0) parts.push(this.getPluralSuffix(hours, i18n.item.details.duration.hour));
		if (minutes > 0) parts.push(this.getPluralSuffix(minutes, i18n.item.details.duration.minute));
		if (seconds > 0) parts.push(this.getPluralSuffix(seconds, i18n.item.details.duration.second));

		return i18n.item.details.duration.every + ' ' + parts.join(' ') || '';
	},
	
	getPluralSuffix: function(num, duration) {
		var curLang = localStorage['csdi-lang'] != null ? localStorage['csdi-lang'] : 'en';
		if (curLang == 'zh-hk' || curLang == 'zh-cn')
			return num + duration;
		else
			return num === 1 ? num + ' ' + duration : num + ' ' + duration + 's';
	}

  };
  
  return oThisObject;
});
