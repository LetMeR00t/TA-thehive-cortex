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
 
           if("thehive_max_cases" in content){
                thehive_max_cases = content["thehive_max_cases"]
            }
            else {
                thehive_max_cases = 100
	    }
 
            if("thehive_sort_cases" in content){
                thehive_sort_cases = content["thehive_sort_cases"]
            }
            else {
                thehive_sort_cases = "-startDate"
	    }
 
    	    // Update default AND submitted tokens
    	    var def_tokens = mvc.Components.get("default");
    	    var sub_tokens = mvc.Components.get("submitted");

            def_tokens.set("max_cases", thehive_max_cases);
            def_tokens.set("form.max_cases", thehive_max_cases);
            def_tokens.set("sort_cases", thehive_sort_cases);
            def_tokens.set("form.sort_cases", thehive_sort_cases);
            sub_tokens.set("max_cases", thehive_max_cases);
            sub_tokens.set("form.max_cases", thehive_max_cases);
            sub_tokens.set("sort_cases", thehive_sort_cases);
            sub_tokens.set("form.sort_cases", thehive_sort_cases);
			
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

    sub_tokens.on("change:create_add_task", function(model, value, options){

	if (typeof value != typeof undefined && value != "") {
            console.log("Add new task: "+value);

	    // Get current tasks and add the new one
	    tasks = mvc.Components.getInstance("input_create_tasks");
	    new_tasks = tasks.val();
	    new_tasks.push(value);

	    // Set the new tags
	    tasks.val(new_tasks);
	    sub_tokens.set("create_tasks",new_tasks.join(" "));

	    // Render all tags
            tasks.render();

	    // clean the input field containing the last task
	    mvc.Components.getInstance("input_create_add_task").val("");
	}

    });


});

