$.widget("ui.styleform", {

	_init : function() {
		var object = this;
		var root = this.element;
		var form = root.find("form");
		var inputs = form.find("input,select,textarea");

		root.find("fieldset").addClass("ui-widget-content ui-corner-all");
		root.find("legend").addClass("ui-widget-header ui-corner-all");
		//form.addClass("ui-widget");
	
		$.each(inputs,function(){
			$(this).addClass('ui-widget-content ui-corner-all');
			
			if($(this).is(":reset ,:submit"))
				object.buttons(this);
			else if($(this).is(":checkbox"))
				object.checkboxes(this);
			else if($(this).is("input[type='text']")||$(this).is("textarea")||$(this).is("input[type='password']"))
				object.textelements(this);
			else if($(this).is(":radio"))
				object.radio(this);
			else if($(this).is("select"))
				object.selector(this);
	
			if($(this).hasClass("date"))
				$(this).datepicker();
		});
	},
	
	textelements : function(element){
		/*$(element).bind({
			focusin: function() {
				$(this).toggleClass('ui-state-focus');
			},
			focusout: function() {
				$(this).toggleClass('ui-state-focus');
			}
		});*/
	},
	
	buttons : function(element) {
		$(element).button();
	},
	
	checkboxes : function(element) {
	
	},
	
	radio : function(element) {
	
	},
	
	selector : function(element) {
	
	}

});
