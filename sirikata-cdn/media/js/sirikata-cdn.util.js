$(document).ready(function() {
	$( "a.button" ).button();
	$("input[type=text].clip_url").mouseup(function(e){
		$(this).select();
	});
	$("#search_submit").button({
        icons: {
            primary: "ui-icon-search"
        },
        text: false
    });
});
