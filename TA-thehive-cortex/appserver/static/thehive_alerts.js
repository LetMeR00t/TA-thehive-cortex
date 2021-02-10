require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Console feedback
    console.log("Get TheHive additional parameters"); 
    console.log("Get TheHive modularinput settings"); 

 
    // Create a service and request a refresh for analyzers
    var service = mvc.createService();
    service.get('TA_thehive_cortex_settings/additional_parameters', "", function(err, response) {
 
        if(err) {
    	// Something is not working during the recovering process
            console.log(response.err);
        }
        else if(response.status === 200) {
            console.log('Response: ', response.data);
 
            content = response.data["entry"][0]["content"];
 
           if("thehive_max_alerts" in content){
                thehive_max_alerts = content["thehive_max_alerts"]
            }
            else {
                thehive_max_alerts = 100
	    }
 
            if("thehive_sort_alerts" in content){
                thehive_sort_alerts = content["thehive_sort_alerts"]
            }
            else {
                thehive_sort_alerts = "-startDate"
	    }
 
    	    // Update default AND submitted tokens
    	    var def_tokens = mvc.Components.get("default");
    	    var sub_tokens = mvc.Components.get("submitted");

            def_tokens.set("max_alerts", thehive_max_alerts);
            def_tokens.set("form.max_alerts", thehive_max_alerts);
            def_tokens.set("sort_alerts", thehive_sort_alerts);
            def_tokens.set("form.sort_alerts", thehive_sort_alerts);
            sub_tokens.set("max_alerts", thehive_max_alerts);
            sub_tokens.set("form.max_alerts", thehive_max_alerts);
            sub_tokens.set("sort_alerts", thehive_sort_alerts);
            sub_tokens.set("form.sort_alerts", thehive_sort_alerts);
			
        }
    
        // Console feedback
        console.log("TheHive additional parameters recovered"); 
 
    })


    // Set configuration for automatically adding a new value for tags and tasks
    var sub_tokens = mvc.Components.get("submitted");

    sub_tokens.on("change:create_add_tag", function(model, value, options){

	if (typeof value != typeof undefined && value != "") {
            console.log("Add new tag: "+value);

	    // Get current tags and add the new one
	    tags = mvc.Components.getInstance("input_create_tags");
	    new_tags = tags.val();
	    new_tags.push(value);

	    // Set the new tags
	    tags.val(new_tags);
	    sub_tokens.set("create_tags",new_tags.join(" "));

	    // Render all tags
            tags.render();

	    // clean the input field containing the last tag
	    mvc.Components.getInstance("input_create_add_tag").val("");
        }

    });


});

