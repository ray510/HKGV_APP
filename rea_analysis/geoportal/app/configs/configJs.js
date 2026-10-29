var site = "OPEN";
var facebookAppId = "791241032172460";
var recaptchaSitekey = "6LcXFPAiAAAAALNPvA-mLjDW1146B9mSqc3Cne5P";

function getSite(){
	return site;
}

if(getSite()=="OPEN"){
	window.fbAsyncInit = function() {
		FB.init({
			appId      : facebookAppId,
			cookie     : true,
			xfbml      : true,
			version    : 'v14.0'
		});
		  
		FB.AppEvents.logPageView();
	};
}

function facebookChangeLang(curLang){
	//facebook change language
	if(typeof curLang === 'undefined' || curLang == null)
		curLang = "en";
	else if(curLang.indexOf('zh-')==0)
		curLang = curLang.replace('zh-','zh_');
	console.log("facebook lang: "+curLang);
		
	(function(d, s, id, lang){
		var js, fjs = d.getElementsByTagName(s)[0];
		if (d.getElementById(id)) {
			$("#"+id).remove();
		}
		js = d.createElement(s);
		js.id = id;
		js.async = true;
		js.src = "https://connect.facebook.net/"+lang+"/sdk.js";
                fjs = d.getElementsByTagName(s)[0];
		fjs.parentNode.insertBefore(js, fjs);
	}(document, 'script', 'facebook-jssdk', curLang));
}

if(getSite()=="OPEN"){
	var onloadCallback = function() {
		grecaptcha.render('field-g-recaptcha', {
		   	'sitekey' : recaptchaSitekey,
		   	'hl' : localStorage["csdi-lang"]
		});
	};
}

function recaptchaCallback(){
	// clear reCAPTCHA
	clearError("g-recaptcha");
}

