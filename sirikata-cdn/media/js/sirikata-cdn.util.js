$(document).ready(function() {
	$( "a.button" ).button();
	$("input[type=text].clip_url").mouseup(function(e){
		$(this).select();
	});
});
