require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Console feedback
    console.log("Get Cortex additional parameters"); 
    console.log("Get Cortex modularinput settings")
 
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

            if("cortex_max_jobs" in content){
                cortex_max_jobs = content["cortex_max_jobs"]
            }
            else {
                cortex_max_jobs = 100
	    }
 
            if("cortex_sort_jobs" in content){
                cortex_sort_jobs = content["cortex_sort_jobs"]
            }
            else {
                cortex_sort_jobs = "-createdAt"
	    }
 
    	    // Update default AND submitted tokens
    	    var def_tokens = mvc.Components.get("default");
    	    var sub_tokens = mvc.Components.get("submitted");

            def_tokens.set("max_jobs", cortex_max_jobs);
            def_tokens.set("form.max_jobs", cortex_max_jobs);
            def_tokens.set("sort_jobs", cortex_sort_jobs);
            def_tokens.set("form.sort_jobs", cortex_sort_jobs);
            sub_tokens.set("max_jobs", cortex_max_jobs);
            sub_tokens.set("form.max_jobs", cortex_max_jobs);
            sub_tokens.set("sort_jobs", cortex_sort_jobs);
            sub_tokens.set("form.sort_jobs", cortex_sort_jobs);
			
			
        }
    
        // Console feedback
        console.log("Cortex additional parameters recovered"); 
 
    })

});

