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
define([],function() {
  return {};
  });

  let curElementName, isPopupLoaded=false;

  function popupResize(){
  	if (isPopupLoaded) domainPopup(null, curElementName);
  }

  function toogleDomainRow(id){
  	$(".domain_id_" + id).toggle();
  	domainClose();
  }

  function domainClose(){
  	$("[id^=domain_popup_]").hide();
  	isPopupLoaded = false;
  }

  function domainPopup(item, elementName){
  	$("[id^=domain_popup_]").hide();
  	
  	const element = $("#img_" + elementName);
  	const offset = $(element).parent().parent().offset();
  	const x = offset.left - $("#absBody").offset().left + 50;
  	const y = offset.top - $("#absBody").offset().top - 80;
  	
  	//console.log("x: " + x + ", y: " + y);

  	$("#domain_popup_" + elementName).css({top: y, left: x, position:'absolute'});	
  	$("#domain_popup_" + elementName).show();
  	
  	curElementName = elementName;
  	isPopupLoaded = true;
  }