(function() {
  // Custom initialization
})();

function setCookie(name,value,dateValue,dateType) {
    var expires = "";
	if (dateType && dateValue){
		var date = new Date();
		switch (dateType) {
			case "year":
				date.setTime(date.getTime() + (dateValue*24*60*60*1000*365));
				break;
			case "month":
				date.setTime(date.getTime() + (dateValue*24*60*60*1000*30));
				break;
			case "day":
				date.setTime(date.getTime() + (dateValue*24*60*60*1000));
				break;
			case "hour":
				date.setTime(date.getTime() + (dateValue*60*60*1000));
				break;
			case "minute":
				date.setTime(date.getTime() + (dateValue*60*1000));
				break;
			case "second":
				date.setTime(date.getTime() + (dateValue*1000));
				break;
		}
		expires = "; expires=" + date.toUTCString();
	}
    document.cookie = name + "=" + (value || "")  + expires + "; path=/";
}

function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for(var i=0;i < ca.length;i++) {
        var c = ca[i];
        while (c.charAt(0)==' ') c = c.substring(1,c.length);
        if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
    }
    return null;
}

function eraseCookie(name) {   
    document.cookie = name +'=; Path=/; Expires=Thu, 01 Jan 1970 00:00:01 GMT;';
}

function winPopup(url){
	var popWindowName = 'Demonstration APIs using ldproxy';
	var features = 'scrollbars,status';
	var winWd = screen.availWidth - 10;
	var winHt = screen.availHeight - 47;
	
	features += ',width=' + winWd + ',height=' + winHt;
	features += ',left=0,top=0';
	window.open(url, popWindowName, features);
}

function checkIsTa(id) {
	var isTa = false;
	var data = { 'datasetId': id };
	$.ajax({
		url: window.location.origin + '/csdi-webpage/getDatasetInfo',
		method: 'GET',
		dataType: 'json',
		contentType: 'application/json',
		async: false,
		data: data,

		success: function(result) {
			isTa = result.datasetInfo.isTa;
		},
		error: function(error) {
			//console.log("Error: " + error);
		},
	});
	return isTa;
}

function _copyLinkFunctionForGeoRss(url){
	try {
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(url);
		} else {
	        let textArea = document.createElement("textarea");
	        textArea.value = url;
	        textArea.style.position = "fixed";
	        textArea.style.left = "-999999px";
	        textArea.style.top = "-999999px";
	        document.body.appendChild(textArea);
	        textArea.focus();
	        textArea.select();
            document.execCommand('copy');
            textArea.remove();
	    }
	}
	catch(ex){
		alert("Error: " + ex);
	}
}

function _copyLinkFunction(url){
	try {
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(url);
		} else {
	        let textArea = document.createElement("textarea");
	        textArea.value = url;
	        textArea.style.position = "fixed";
	        textArea.style.left = "-999999px";
	        textArea.style.top = "-999999px";
	        document.body.appendChild(textArea);
	        textArea.focus();
	        textArea.select();
            document.execCommand('copy');
            textArea.remove();
	    }
		
		$("#linkCopiedAlert").css("display", "block");
		
		setTimeout(function() {
		    $("#linkCopiedAlert").css("display", "none");
		}, 1000);
	}
	catch(ex){
		$("#linkCopyFailedAlertContent").html(url);
		$("#linkCopyFailedAlert").css("display", "block");
		
		$("#linkCopyFailedAlertClose").click(function(){
			$("#linkCopyFailedAlert").css("display", "none");
		});
	}
}

function _copyKeywordFunction(keyword){
		if (navigator.clipboard && window.isSecureContext) {
			navigator.clipboard.writeText(keyword);
		} else {
	        let textArea = document.createElement("textarea");
	        textArea.value = keyword;
	        textArea.style.position = "fixed";
	        textArea.style.left = "-999999px";
	        textArea.style.top = "-999999px";
	        document.body.appendChild(textArea);
	        textArea.focus();
	        textArea.select();
            document.execCommand('copy');
            textArea.remove();
	    }
		
		$("#keywordCopiedAlert").css("display", "block");
		
		setTimeout(function() {
		    $("#keywordCopiedAlert").css("display", "none");
		}, 1000);
	
}

function toggleText() {
	if (document.getElementById("preview").style.display == "inline"){
		document.getElementById("preview").style.display = "none";
		document.getElementById("hiddenText").style.display = "inline";
		document.getElementById("readmore").style.display = "none";
		document.getElementById("readless").style.display = "flex";
	}else{
		document.getElementById("preview").style.display = "inline";
		document.getElementById("hiddenText").style.display = "none";
		document.getElementById("readmore").style.display = "flex";
		document.getElementById("readless").style.display = "none";

	}
}

function toggleTextCons(i) {
	if (document.getElementById("Conspreview_" + i).style.display == "inline"){
		document.getElementById("Conspreview_" + i).style.display = "none";
		document.getElementById("ConshiddenText_" + i).style.display = "inline";
		document.getElementById("con_readmore_" + i).style.display = "none";
		document.getElementById("con_readless_" + i).style.display = "flex";
	}else{
		document.getElementById("Conspreview_" + i).style.display = "inline";
		document.getElementById("ConshiddenText_" + i).style.display = "none";
		document.getElementById("con_readmore_" + i).style.display = "flex";
		document.getElementById("con_readless_" + i).style.display = "none";		
	}
}

function toggleTextKeywords() {
	if (document.getElementById("previewKey").style.display == "inline"){
		document.getElementById("previewKey").style.display = "none";
		document.getElementById("hiddenTextKey").style.display = "inline";
		document.getElementById("otherKeywordsreadmore").style.display = "none";
		document.getElementById("otherKeywordsreadless").style.display = "inline";
	}else{
		document.getElementById("previewKey").style.display = "inline";
		document.getElementById("hiddenTextKey").style.display = "none";
		document.getElementById("otherKeywordsreadmore").style.display = "inline";
		document.getElementById("otherKeywordsreadless").style.display = "none";
	}
}

function keywordsToggle() {
	if (document.getElementById("otherKeywords_keywords_readmore").style.display == "block"){
		document.getElementById("otherKeywords_keywords_readmore").style.display = "none";
		document.getElementById("otherKeywords_keywords_readless").style.display = "block";
		document.getElementById("keywordsReadMore").style.display = "flex";
		document.getElementById("keywordsReadLess").style.display = "none";
	}else{
		document.getElementById("otherKeywords_keywords_readmore").style.display = "block";
		document.getElementById("otherKeywords_keywords_readless").style.display = "none";
		document.getElementById("keywordsReadMore").style.display = "none";
		document.getElementById("keywordsReadLess").style.display = "flex";
	}
}

function otherResToggle() {
	if (document.getElementById("otherRes_readmore").style.display == "flex"){
		document.getElementById("otherRes_readmore").style.display = "none";
		document.getElementById("otherRes_readless").style.display = "flex";
		document.getElementById("otherResTextLess").style.display = "none";
		document.getElementById("otherResText").style.display = "block";
	}else{
		document.getElementById("otherRes_readmore").style.display = "flex";
		document.getElementById("otherRes_readless").style.display = "none";
		document.getElementById("otherResTextLess").style.display = "block";
		document.getElementById("otherResText").style.display = "none";
	}
}

function constraintsHandle(id, type, moretext, lesstext) {
	if (type == 'usageConstraints'){
		$('#usageConstraints').show();
		$('#legalConstraints').hide();
		$('#securityConstraints').hide();
	}else if(type == 'legalConstraints'){
		$('#legalConstraints').show();
		$('#usageConstraints').hide();
		$('#securityConstraints').hide();
	}else if(type == 'securityConstraints'){
		$('#securityConstraints').show();
		$('#usageConstraints').hide();
		$('#legalConstraints').hide();
	}
	document.getElementById("dataremark_topnav").getElementsByClassName("active")[0].classList.remove("active");
	document.getElementById(id).classList.add("active");
}

function buttonDisabledToggle(id, status) {
	if (status == true){
		$('#' + id).attr('disabled', true);
		$('#' + id).css('opacity', '0.4');
	}else{
		$('#' + id).attr('disabled', false);
		$('#' + id).css('opacity', '1');	
	}
}