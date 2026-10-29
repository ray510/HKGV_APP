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
        "dojo/topic",
        "app/context/app-topics",
        "dojo/router",
		"dojo/dom-style",
		"dojo/dom-construct",
        "app/common/Templated",
        "dojo/text!./templates/App.html",
        "dojo/i18n!../nls/resources",
		"dojo/io-query",
		"dojo/on",
		"dojo/dom",
        "app/etc/util",
        "app/main/SearchPanel",
        "app/main/MapPanel",
        "app/main/AboutPanel",
        "app/content/MetadataEditor",
        "app/content/UploadMetadata",
		"app/main/MetadataInfoPanel",
        "app/search/MetadataInfoPane",
		"app/context/AppClient",],
function(declare, lang, array, topic, appTopics, router, domStyle, domConstruct, Templated, template, i18n, ioQuery, on, dom, util, SearchPanel, MapPanel, AboutPanel,
    MetadataEditor, UploadMetadata, MetadataInfoPanel, MetadataInfoPane, AppClient) {

  var oThisClass = declare([Templated], {

    i18n: i18n,
    templateString: template,

    postCreate: function() {
      this.inherited(arguments);
      var self = this;
      this.updateUI();

      var ignoreMapPanelActivated = false;
      var navName = 'Null';
	  
	  util.update_header(navName);

      //alert(i18n.lang);
      router.register("searchPanel", lang.hitch(this, function(evt){
        this.setHash("searchPanel");

        // //console.log("searchpanel clicked");
        var curLang = localStorage["csdi-lang"] != null ? localStorage["csdi-lang"] : "en";
        var lastMapLang = localStorage["csdi-maplang"] ;

        if (lastMapLang != null && lastMapLang != curLang) {
         	window.location.href = "#searchPanel";
			$('#allPanel').css('opacity', 0);
        	location.reload();
        }
		  
      	if (util.getRequestParam("provider") || util.getRequestParam("cat") || util.getRequestParam("key"))
			sessionStorage.removeItem("csdi-filter");
        navName = 'cat';
		util.switchPanel('searchPanel');
		show_footer(); 
      }));
	  
	  router.register("mapPanelJs4", lang.hitch(this, function(evt){
	      util.switchPanel('mapPanelJs4');
	      navName = 'mapJs4';
		  hide_footer();
	    }));

      router.register("mapPanel", lang.hitch(this, function(evt){
        if (!ignoreMapPanelActivated && !this.mapPanel.mapWasInitialized) {
          this.mapPanel.ensureMap();
        }
        util.switchPanel('mapPanel');
        navName = 'map';
		hide_footer();
      }));

	  router.register("metadataInfoPanel", lang.hitch(this, function(evt){
	    util.switchPanel('metadataInfoPanel');
        navName = 'met';
		show_footer();
      }));

      router.register("aboutPanel", lang.hitch(this, function(evt){
        $("a[href='#aboutPanel']").tab("show");
      }));

      router.register("3dmapInfoPanel", lang.hitch(this, function (evt) {
        //console.log("Load 3d Map on geoportal");
        $("a[href='#3dmapInfoPanel']").tab("show");
		util.switchPanel('3dmapInfoPanel');
        if (!document.getElementById('cesiumContainer')) $('#3dmap-mappanel').load("app/3dmap/index.html");
		hide_footer();
      }));

      router.startup();

      if (sessionStorage.getItem("3dLayerList")) { 
        sessionStorage.removeItem("3dLayerList")
      }

      if (sessionStorage.getItem("currentmap")) { 
        sessionStorage.removeItem("currentmap")
      }

	  // metadata information
	  var isGoToMetadataInfo = false;
	  var windowsUri = window.location.href;
      if (windowsUri.indexOf("?") !== -1) {
      	var s = windowsUri.substring(windowsUri.indexOf("?")+1,windowsUri.length);
        var hash = s.indexOf("#")>=0? s.substring(s.indexOf("#")+1,s.length): "";
        s= s.indexOf("#")>=0? s.substring(0,s.indexOf("#")): s;

		var o = ioQuery.queryToObject(s);

		if(o && typeof o.datasetId === "string"){
			isGoToMetadataInfo = true;

			navName = 'met';

			var uri = "./rest/metadata/item/" + o.datasetId;
			var csdiToken = sessionStorage['csdi-geoportal-token'];
			if(typeof csdiToken !== "undefined" && csdiToken!=null && csdiToken!=""){
				var tokenJson = JSON.parse(csdiToken);
				if(typeof tokenJson.access_token !== "undefined" && tokenJson.access_token!=null && tokenJson.access_token!=""){
					uri = uri + "?access_token=" + tokenJson.access_token;
				}
			}
			$.ajax({
				type: "GET",
				url: uri,
		        async: false,
				success : function(result) {
					item = result;

					if(typeof item !== "undefined" && item!=null){
						util.activeMetatdataInfoMenu();
        				router.go("metadataInfoPanel");
					}
					else {
						router.go("searchPanel");
					}
				},
				error: function(xhr, statusText, err){
					if (xhr.responseJSON.error.message == 'Id not found.') {
						$('#datasetNotFoundModal').modal('show');
					} else {
						// check isLogin or not
						if (AppContext.appUser.isSignedIn()) {
							$('#accessDeniedModal').modal('show');
						} else {
							sessionStorage.setItem('redirectURL', window.location.href);
							$('#loginRequiredModal').modal('show');
						}
					}
					//router.go("searchPanel");
		        }
			});
		} else if (o && typeof o.lang === "string"){
			router.go("searchPanel");
		}
      }

      if (!isGoToMetadataInfo && (!location.hash || location.hash.length==0)) {
		var v = '';
		var isFSDT = false; 
		var temp = {};
		var tempObj = [];
		var key=util.getRequestParam("key");
		if (key != null) {
			v=key;
			temp = {
				displayVal: v,
			    field: 'bool',
				query: util.getESQuery(v),
			    value: v
			};
			tempObj.push(temp);
		}
		
		var provider=util.getRequestParam("provider");
	    if (provider != null) {
			v=provider;
			temp = {
				displayVal: v,
			    field: 'contact_organizations_s',
			    value: v
			};
			tempObj.push(temp);
		}
	
		// Support Category Search (Override Provider search)
		var cat=util.getRequestParam("cat");
		if (cat != null) {
			if (cat.indexOf("FSDT") > 0) isFSDT = true;
			v=cat;
			
			if (isFSDT){
				temp = {
				    displayVal: v,
				    field: 'themes_s',
				    value: v
				};
			}else{
				temp = {
				    displayVal: v,
				    field: 'categories_s',
				    value: v
				};
			}
			tempObj.push(temp);
	      }
		if (tempObj.length > 0)
		sessionStorage['csdi-filter'] = JSON.stringify(tempObj);
		history.replaceState(location.pathname, document.title, location.pathname.replace(/\/+$/g, "") + "/#searchPanel");
        this.setHash("searchPanel");
        router.go("searchPanel");
      }

      $("a[href='#searchPanel']").on("shown.bs.tab",lang.hitch(this, function(e) {
        this.setHash("searchPanel");

        // //console.log("searchpanel clicked");
        var curLang = localStorage["csdi-lang"] != null ? localStorage["csdi-lang"] : "en";
        var lastMapLang = localStorage["csdi-maplang"] ;

        if (lastMapLang != null && lastMapLang != curLang) {
         	window.location.href = "#searchPanel";
			$('#allPanel').css('opacity', 0);
        	location.reload();
        } else {
             router.go("searchPanel");
           }
      }));
      $("a[href='#mapPanel']").on("shown.bs.tab",lang.hitch(this, function(e) {
        router.go("mapPanel");
      }));
	  $("a[href='#metadataInfoPanel']").on("shown.bs.tab",lang.hitch(this, function(e) {
        router.go("metadataInfoPanel");
      }));
        $("a[href='#metadataInfoPanel']").on("click",lang.hitch(this, function(e) {
            navName = 'met';
            //router.go("metadataInfoPanel");
            //window.alert(sessionStorage.getItem("selectedItem"));
			var curLang = localStorage["csdi-lang"] != null ? localStorage["csdi-lang"] : "en";
        	var lastMapLang = localStorage["csdi-maplang"];

			if (lastMapLang != null && lastMapLang != curLang) {
         		window.location.href = "#metadataInfoPanel";
				$('#allPanel').css('opacity', 0);
        		location.reload();
        	} else {
             	var metadataInfoPane = new MetadataInfoPane({
                checkUrl: false
	            });
	            metadataInfoPane.startup();
	            var uri = "./rest/metadata/item/" + sessionStorage.getItem("selectedItem").split("=")[1];
	            metadataInfoPane.showDataFromClick(metadataInfoPane.item, uri);
	
	            // metadata info panel
	            util.activeMetatdataInfoMenu();
	
	            router.go("metadataInfoPanel");
           	}
        }));      
	
	$("a[href='#aboutPanel']").on("shown.bs.tab",lang.hitch(this, function(e) {
        router.go("aboutPanel");
      }));


      topic.subscribe(appTopics.AddToMapClicked,lang.hitch(this, function(params){
        if (self.mapPanel.mapWasInitialized) {
          //router.go("mapPanel");
          self._onMap();
          self.mapPanel.addToMap(params);
        } else {
          var urlParams = params.token ? {resource: params.type+":"+this.normalizeUrl(params.url),title:params.title,datasetid:params.id,zhtitle:params.zhtitle,entitle:params.entitle,cntitle:params.cntitle,token:params.token} 
				: {resource: params.type+":"+this.normalizeUrl(params.url),title:params.title,datasetid:params.id,zhtitle:params.zhtitle,entitle:params.entitle,cntitle:params.cntitle};
          ignoreMapPanelActivated = true;
          //router.go("mapPanel");
          self._onMap();
          self.mapPanel.ensureMap(urlParams);
          ignoreMapPanelActivated = false;
        }
      }));

      topic.subscribe(appTopics.SignedIn,function(params){
        self.updateUI();
      });

      $("#idAppDropdown").on("show.bs.dropdown",function() {
        self.updateUI();
      });

	  /*if(typeof metadataItemId == "string") {
		var metadataInfoPanel = new MetadataInfoPanel();
		metadataInfoPanel._startPane(metadataItemId);
	  }*/

     if (navName == 'cat' || navName == 'met')   show_footer();
	 else hide_footer();

     // Close Menu if still pop up
     on(dom.byId("overlay"), "click", close_top_nav);
     on(dom.byId("allPanel"), "wheel", close_top_nav);
     on(dom.byId("allPanel"), "touchstart", close_top_nav);
	 document.querySelector('.g-app').onwheel = function() {  
		 close_top_nav();
 
	 };

	// Change text when different size
	if(getSite() == "OPEN") {
	    $('#ftTNC').text(i18n.footer.ftTNC);
	} else {
	    $('#ftTNC').text(i18n.footer.ftNotice);
	}
		
		var item = {
	        'paraSite': getSite(),
			'paraName': 'VERSION'
	  	};
	
		var host = window.location.protocol + '//' + window.location.host;
		
		$.ajax({
			url: host + '/csdi-webpage/version',
			method:'GET',
			dataType:'json',
			contentType: 'application/json',
			data:item,
			
			success:function(res){
				try{
					$(".ftVersion").text('Ver. ' + res.sysParameter[0].paraValue);
					////console.log(res);
				}catch (e){
					$(".ftVersion").text('Unknown');
				}
			},
	  		error:function(err){
				$(".ftVersion").text('Unknown');
				////console.log(err);
			},
		});
		
		//	New update in profile
		
		var count = sessionStorage.getItem('updateCount');
		$('#newUpdateCount').text(count);
		if(count > 0 || count == '!'){
			$('#newUpdate-div').css('display','block');
			$('#newUpdate-div-menu').css('display','inline-flex');
		}else{
			$('#newUpdate-div').css('display','none');
			$('#newUpdate-div-menu').css('display','none');
		}
		
		// AutoComplete for searching
		var timer;
		this.own(
		    on(dom.byId("welcome_search"), "keyup", lang.hitch(this, function() {
		        timer && clearTimeout(timer);
		        timer = setTimeout(lang.hitch(this, this.fnSearchResult), 200);
		    }))
		);
		
		var countdownTimer;
		
		// Listen for messages coming from the iframe (JS4)
		$(window).on("message", function(e) {
			var msg = e.originalEvent.data;
			var origin = e.originalEvent.origin;

			// check origin
			if (origin !== window.location.origin) {
				console.log("Untrusted origin →", origin);
				return;
			}
			
			if (msg.action != "goDetailPage") {
				console.log("Not go to detail page, but for ", msg.action);
				return;
			}

			sessionStorage.setItem('selectedItem', 'datasetId=' + msg.identifier);
			var item;
			var uri = "./rest/metadata/item/" + encodeURIComponent(msg.identifier);
			$.ajax({
				type: "GET",
				url: uri,
				async: false,
				success : function(result) {
					item = result;
				},
				error: function(xhr, statusText, err){
					console.log("Error metadata:" + err);
				},
				complete: () => {
					if (AppContext.geoportal.supportsApprovalStatus ||
			        AppContext.geoportal.supportsGroupBasedAccess) {
				        var client = new AppClient();
				        uri = client.appendAccessToken(uri);
				    }
				    var metadataInfoPane = new MetadataInfoPane({
				        checkUrl: false
				    });
					$("#idCatalogTitle").click();
					
				    metadataInfoPane.startup();
				    metadataInfoPane.showData(item, uri);
				    // metadata info panel
				    util.activeMetatdataInfoMenu();
				    router.go("metadataInfoPanel");
					$('#welcome_search').val('');
					domConstruct.empty(dojo.byId("searchResult"));
					sessionStorage.removeItem('search');
					
					if (msg.goExplorer){
						setTimeout(function() {
							$('[data-dojo-attach-point="exploreButtonNode"]').click();
							$("#idMapTitleJs4").click();
						}, 300);						
						
					}
				}
			});
		});

		function startCountdown(seconds, element) {
	        clearInterval(countdownTimer);
	        $(element).find('.modal-timer').text('(' + seconds + ')');
	
	        countdownTimer = setInterval(function() {
	            seconds -= 1;
	            $(element).find('.modal-timer').text('(' + seconds + ')');
	
	            if (seconds === 0) {
	                clearInterval(countdownTimer);
	                $(element).find('.modal-timer').text('');
					window.location.href = location.origin + '/csdi-webpage';
	            }
	        }, 1000);
	    }
		
		$('#welcome_search').focusin(function(){
			document.getElementById("searchResult-container").style.display = "block";
		});
		
		$('#welcome_search').focusout(function(){
			hideTimer = setTimeout(function() {
				document.getElementById("searchResult-container").style.display = "none";
			}, 200);
		});
		
		$('#btnDatasetNotFound').click(function() {
			window.location.href = location.origin + '/csdi-webpage';
		});
		
		$('#btnLoginRequired').click(function(){
			window.location.href = location.origin + '/csdi-webpage/login';
		});
		
		$('#btnAccessDenied').click(function(){
			window.location.href = location.origin + '/csdi-webpage';
		});
		
		$('#datasetNotFoundModal').on('shown.bs.modal', function() {
		    startCountdown(30, this);
		});
		
		$('#loginRequiredModal').on('shown.bs.modal', function() {
	        startCountdown(30, this);
	    });

		$('#accessDeniedModal').on('shown.bs.modal', function() {
	        startCountdown(30, this);
	    });
		
		$("#datasetNotFoundModal").on('hidden.bs.modal', function(){
			window.location.href = location.origin + '/csdi-webpage';
		});
		
		$("#loginRequiredModal").on('hidden.bs.modal', function(){
	    	window.location.href = location.origin + '/csdi-webpage';
		});
		
		$("#accessDeniedModal").on('hidden.bs.modal', function(){
	    	window.location.href = location.origin + '/csdi-webpage';
		});
		
		this._tooltipTimeouts = new Map();

		topic.subscribe(appTopics.CopyURLToClipboard, ({ widget, target, url }) => {
			this.copyURLToClipboard(widget, target, url);
		});

		topic.subscribe(appTopics.ClearTooltips, ({ widget }) => {
			this.clearTooltips(widget);
		});
    },

	destroy: function () {
		this.clearAllTooltips();

		this.inherited(arguments);
	},


    /* =================================================================================== */
    setHash: function(hash) {
      var el = document.getElementById(hash);
      var id = el.id;
      el.removeAttribute('id');
      location.hash = hash;
      el.setAttribute('id',id);
   },

    createMetadataClicked: function() {
      var editor = new MetadataEditor();
      editor.show();
    },

    signInClicked: function() {
      AppContext.appUser.showSignIn();
    },

    signOutClicked: function() {
      AppContext.appUser.signOut();
    },

    uploadClicked: function() {
      if (AppContext.appUser.isPublisher()) (new UploadMetadata()).show();
    },

    editFacetClicked: function() {
      console.warn("TODO provide edit facet functionality in App.js")
    },

    /* =================================================================================== */

    getCreateAccountUrl: function() {
      if (AppContext.geoportal && AppContext.geoportal.createAccountUrl) {
        return util.checkMixedContent(AppContext.geoportal.createAccountUrl);
      }
      return null;
    },

    updateUI: function() {
      var updateHref = function(node,link,href) {
        if (typeof href === "string" && href.length > 0) {
          link.href = href;
          node.style.display = "";
        } else {
          link.href = "javascript:void(0)";
          node.style.display = "none";
        }
      };
      var v;
      if (AppContext.appUser.isSignedIn()) {
        v = i18n.nav.welcomePattern.replace("{name}",AppContext.appUser.getUsername());
        util.setNodeText(this.usernameNode,v);
        this.userOptionsNode.style.display = "";
        this.signInNode.style.display = "none";
        this.signOutNode.style.display = "";
        this.adminOptionsBtnNode.style.display = "";
        updateHref(this.createAccountNode,this.createAccountLink,null);
        updateHref(this.myProfileNode,this.myProfileLink,AppContext.appUser.getMyProfileUrl());
      } else {
        this.usernameNode.innerHTML = "";
        this.userOptionsNode.style.display = "none";
        this.createAccountNode.style.display = "none";
        this.signInNode.style.display = "";
        this.signOutNode.style.display = "none";
        this.adminOptionsBtnNode.style.display = "none";
        updateHref(this.createAccountNode,this.createAccountLink,this.getCreateAccountUrl());
        updateHref(this.myProfileNode,this.myProfileLink,null);

      }

      var isAdmin = AppContext.appUser.isAdmin();
      var isPublisher = AppContext.appUser.isPublisher();
      $("li[data-role='admin']").each(function(i,nd) {
        if (isAdmin) nd.style.display = "";
        else nd.style.display = "none";
      });
      $("li[data-role='publisher']").each(function(i,nd) {
        if (isPublisher) nd.style.display = "";
        else nd.style.display = "none";
      });

      if (!FileReader) this.uploadNode.style.display = "none";

      // Set Lang Button
      var curLang = localStorage["csdi-lang"];
	  if (curLang == null || curLang == 'en') {
		this.LangENNode.style.display = "none";
		this.LangTCNode.style.display = "block";
		this.LangSCNode.style.display = "block";
	 }
	  if (curLang == 'zh-hk') {
		this.LangENNode.style.display = "block";
		this.LangTCNode.style.display = "none";
		this.LangSCNode.style.display = "block";
	 }
	 if (curLang == 'zh-cn') {
		this.LangENNode.style.display = "block";
		this.LangTCNode.style.display = "block";
		this.LangSCNode.style.display = "none";
	 }

    },

    normalizeUrl: function(url) {
      var services = ["wmsserver", "mapserver", "imageserver", "featureserver", "streamserver", "vectortileserver"];
      var selSrv = array.filter(services, function(srv) { return url.toLowerCase().indexOf(srv)>=0; });
      if (selSrv && selSrv.length>0) {
        var srv = selSrv[0];
        url = url.substr(0, url.toLowerCase().indexOf(srv) + srv.length);
      }
      return url;
    },

    _onHome: function() {
      this.searchPanelLink.click()
      location.hash = "searchPanel"
    },

	_onMap: function() {
	  $('#idMenuTitle').removeClass('active');
	  $('#idCatalogTitle').removeClass('active');
	  $('#idMapTitle').addClass('active');
	  $('#idMetadataInfoTitle').removeClass('active');

      hide_footer();
      router.go("mapPanel");
    },

	fnSearchResult: function() {
		document.getElementById("searchResult-container").style.display = "block";
		if ($('#welcome_search').val().length > 0){
			var value = $('#welcome_search').val().replace(/\s{2,}/g, ' ').replace(/\s+$/g, '');
			var searchUrl = window.location.origin + '/csdi-webpage/searchDataset?search_query=' + encodeURIComponent(value);
			if (sessionStorage['search'] == null) sessionStorage.setItem('search', value);
			if (value != sessionStorage['search'] || $('#searchResult').html() == '') {
			    $.ajax({
			        type: "GET",
			        url: searchUrl,
			        async: false,
			        success: (result) => {
			            var searchResultArr = [];
						var curLang = localStorage['csdi-lang'];
			            if (result.searchResult != null) {
			                if (result.searchResult.length > 0) {
								domConstruct.empty(dojo.byId("searchResult"));
			                    var searchResultStr = "";
			                    for (var i = 0; i < result.searchResult.length; i++) {
			                       if (result.searchResult[i].searchType == 'dataset'){
										searchResultStr = result.searchResult[i].datasetNameEN;
										if ((curLang == 'en' || curLang == null) && result.searchResult[i].datasetNameEN.toUpperCase().indexOf(value.toUpperCase()) != -1)
											searchResultStr = result.searchResult[i].datasetNameEN;
										else if (curLang == 'zh-hk' && result.searchResult[i].datasetNameTC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].datasetNameTC;
										else if (curLang == 'zh-cn' && result.searchResult[i].datasetNameSC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].datasetNameSC;
										else if (result.searchResult[i].datasetNameEN.toUpperCase().indexOf(value.toUpperCase()) != -1)
											searchResultStr = result.searchResult[i].datasetNameEN;
										else if (result.searchResult[i].datasetNameTC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].datasetNameTC;
										else if (result.searchResult[i].datasetNameSC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].datasetNameSC;
									}else{
										searchResultStr = result.searchResult[i].searchResultEN;
										if ((curLang == 'en' || curLang == null) && result.searchResult[i].searchResultEN.toUpperCase().indexOf(value.toUpperCase()) != -1)
											searchResultStr = result.searchResult[i].searchResultEN;
										else if (curLang == 'zh-hk' && result.searchResult[i].searchResultTC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].searchResultTC;
										else if (curLang == 'zh-cn' && result.searchResult[i].searchResultSC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].searchResultSC;
										else if (result.searchResult[i].searchResultEN.toUpperCase().indexOf(value.toUpperCase()) != -1)
											searchResultStr = result.searchResult[i].searchResultEN;
										else if (result.searchResult[i].searchResultTC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].searchResultTC;
										else if (result.searchResult[i].searchResultSC.indexOf(value) != -1)
											searchResultStr = result.searchResult[i].searchResultSC;
									}
			                        searchResultArr.push(searchResultStr);
			
			                        var currentIndex = 0;
			                        var highlight = "";
									var tempResultStr = searchResultStr;
									var valueArr = value.split(" ");
			                        if (tempResultStr.toUpperCase().indexOf(value.toUpperCase()) != -1) {
										currentIndex = tempResultStr.toUpperCase().indexOf(value.toUpperCase());
			                            highlight = tempResultStr.slice(0, currentIndex) + '<strong>' + tempResultStr.slice(currentIndex, currentIndex + value.length) + '</strong>' +
			                                tempResultStr.slice(currentIndex + value.length);
			                        }else{
			                            for (var j=0;j<valueArr.length;j++){
			                                if (valueArr[j].trim() != "") {
												currentIndex = tempResultStr.toUpperCase().indexOf(valueArr[j].toUpperCase());
			                                    if (currentIndex != -1){
													highlight += tempResultStr.slice(0, currentIndex) + '<strong>' + tempResultStr.slice(currentIndex, currentIndex + valueArr[j].length) + '</strong>';
													tempResultStr = tempResultStr.slice(currentIndex + valueArr[j].length);	
												}else{
													tempResultStr = '';
												}
			                                }
			                            }
			                            highlight += tempResultStr.slice(0);
			                        }

									if (highlight != ''){
										var type = result.searchResult[i].searchType;
										if (result.searchResult[i].searchType == 'dataset'){
											if (curLang == 'zh-hk') type = '數據集';
											else if (curLang == 'zh-cn') type = '数据集';
										}else if (result.searchResult[i].searchType == 'category'){
											if (curLang == 'zh-hk') type = '分類';
											else if (curLang == 'zh-cn') type = '分类';
										}else{
											if (curLang == 'zh-hk') type = '提供機構';
											else if (curLang == 'zh-cn') type = '提供机构';
										}
				                        var url = "";
				                        if (result.searchResult[i].searchType == 'dataset') url = location.origin + '/geoportal?datasetId=' + result.searchResult[i].datasetId;
				                        else if (result.searchResult[i].searchType == 'category') url = location.origin + '/geoportal/?from=0&size=10&cat=' + result.searchResult[i].searchResultEN;
				                        else url = location.origin + '/geoportal/?from=0&size=10&provider=' + result.searchResult[i].searchResultEN;
										
										var li = domConstruct.create("li", {
										    title: searchResultStr
										}, dojo.byId("searchResult"));
									
										if (result.searchResult[i].searchType == 'dataset'){
											domConstruct.create("a", {
											    href: 'javascript:void(0);',
											    style: 'display: flex;',
												value: result.searchResult[i].datasetId,
												innerHTML: '<div class="' + result.searchResult[i].searchType + '">' + type + '</div><span>' + highlight + '</span>',
												onclick: function() {
													sessionStorage.setItem('selectedItem', 'datasetId=' + this.value);
													var item;
													var uri = "./rest/metadata/item/" + encodeURIComponent(this.value);
													$.ajax({
														type: "GET",
														url: uri,
														async: false,
														success : function(result) {
															item = result;
														},
														error: function(xhr, statusText, err){
															console.log("Error:" + err);
														},
														complete: () => {
															if (AppContext.geoportal.supportsApprovalStatus ||
													        AppContext.geoportal.supportsGroupBasedAccess) {
														        var client = new AppClient();
														        uri = client.appendAccessToken(uri);
														    }
														    var metadataInfoPane = new MetadataInfoPane({
														        checkUrl: false
														    });
														    metadataInfoPane.startup();
														    metadataInfoPane.showData(item, uri);
														    // metadata info panel
														    util.activeMetatdataInfoMenu();
														    router.go("metadataInfoPanel");
															topic.publish(appTopics.SetSearchQueryFieldValue, { value: '' });
															domConstruct.empty(dojo.byId("searchResult"));
															sessionStorage.removeItem('search');
														}
													});
												}
											}, li);
										}else{
											var val = '';
											if (result.searchResult[i].searchType == 'category') val = 'categories_s;' + result.searchResult[i].searchResultEN + ';';
											else val = 'contact_organizations_s;' + result.searchResult[i].searchResultEN + ';';
											if (curLang == 'zh-hk') val += result.searchResult[i].searchResultTC;
											else if (curLang == 'zh-cn') val += result.searchResult[i].searchResultSC;
											else val += result.searchResult[i].searchResultEN;
											domConstruct.create("a", {
											    href: 'javascript:void(0);',
											    style: 'display: flex;',
												value: val,
												innerHTML: '<div class="' + result.searchResult[i].searchType + '">' + type + '</div><span>' + highlight + '</span>',
												onclick: lang.hitch(this, function (event) {
													var data = event.currentTarget.value.split(';');
													var field = data[0];
													var term = data[1];
													topic.publish(appTopics.SetSearchQueryFieldValue, { value: '' });
													domConstruct.empty(dojo.byId("searchResult"));
													sessionStorage.removeItem('search');
													topic.publish(appTopics.SelectSearchFilterTerm, { field, term });
												})
											}, li);
										}
									}else{
									document.getElementById('searchResult').innerHTML = '';
									}
			                    }
			                } else {
			                    document.getElementById('searchResult').innerHTML = '';
			                }
			            }
			            else {
			                document.getElementById('searchResult').innerHTML = '';
			            }
			        },
			        error: function (xhr, statusText, err) {
			            console.log("Error:" + err);
			        }, complete: function () {
			            $('#searchResult li').show();
			            sessionStorage.setItem('search', value);
			        }
			    });
			}
		}else{
			$('#searchResult li').hide();
		}
	},

	copyURLToClipboard: function (widget, target, url) {
		window.writeTextToClipboard(url).then(() => {
			const timeoutId = this._tooltipTimeouts.get(widget)?.get(target);

			if (!timeoutId) {
				$(target)
					.tooltip({
						customClass: 'g-app__copy-url-tooltip',
						fallbackPlacements: ['top', 'bottom'],
						offset: [0, 14],
						selector: true, // stop bootstrap from removing the title attribute
						title: i18n.item.details.linkCopied,
						trigger: 'manual',
					})
					.tooltip('show');
			} else {
				clearTimeout(timeoutId);
			}

			if (!this._tooltipTimeouts.has(widget)) {
				this._tooltipTimeouts.set(widget, new Map());
			}

			this._tooltipTimeouts.get(widget).set(
				target,
				setTimeout(
					() => {
						$(target).tooltip('hide');
						this._tooltipTimeouts.get(widget).delete(target);
					},
					3000
				)
			);
		});
	},

	clearTooltips: function (widget) {
		const timeouts = this._tooltipTimeouts.get(widget);

		if (!timeouts) {
			return;
		}

		for (const [target, timeoutId] of timeouts) {
			clearTimeout(timeoutId);
			$(target).tooltip('hide');
		}

		this._tooltipTimeouts.delete(widget);
	},

	clearAllTooltips: function () {
		for (const [widget, timeouts] of this.tooltipTimeouts) {
			this.clearTooltips(widget);
		}
	},


  });

  return oThisClass;
});

function close_top_nav() {
	document.getElementById("csdi-top-nav").style.display = "none";
	var lay = document.getElementById("overlay");
	if (lay){
		document.getElementById('overlay').style.display = "none";}
	$('#idMenuTitle').removeClass('active');
}

function tigger_menu() {
	if (document.getElementById("csdi-top-nav").style.display == "none") {
	  document.getElementById("csdi-top-nav").style.display = "block";
	var lay = document.getElementById("overlay");
	if (lay){
	  document.getElementById('overlay').style.display = "block";}
	  $('#idMapTitle').removeClass('active');
	  $('#idCatalogTitle').removeClass('active');
	  $('#menuMetadataInfoTitle').removeClass('active');
	  return;
	}

	if (document.getElementById("csdi-top-nav").style.display == "block") {
	  document.getElementById("csdi-top-nav").style.display = "none";
	  var lay = document.getElementById("overlay");
	  if (lay){
	  document.getElementById('overlay').style.display = "none";}
	  $('#idMenuTitle').removeClass('active');
	  return;
	}
}

function set_csdi_url(url) {
   var url = '/csdi-webpage/' + url;
   var sInx = url.toLowerCase().indexOf(';jsessionid=');
   if (location.protocol == 'https:' || sInx >=0) return (url);

   var sid = localStorage["csdi-sid"];
   if (sid == null || sid.length < 1) return (url);

   return (url + ';jsessionid=' + sid);
}

function go_csdi_page(url) {
	window.location = set_csdi_url(url);
}

function show_footer() {
	$('.site-footer').show();
}

function hide_footer() {
	$('.site-footer').hide();
}
