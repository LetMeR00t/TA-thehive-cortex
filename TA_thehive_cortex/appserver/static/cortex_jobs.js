require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Console feedback
    console.log("Get cortex settings"); 
 
    // Create a service and request a refresh for analyzers
    var service = mvc.createService();
    service.get('TA_thehive_cortex_settings/cortex', "", function(err, response) {
 
        if(err) {
    	// Something is not working during the recovering process
            console.log(response.err);
        }
        else if(response.status === 200) {
            console.log('Response: ', response.data);
 
            content = response.data["entry"][0]["content"];
 
    	    // Update default AND submitted tokens
    	    var def_tokens = mvc.Components.get("default");
    	    var sub_tokens = mvc.Components.get("submitted");

            var list = [def_tokens, sub_tokens]
	    for (const t in list) {
                list[t].set("cortex_protocol", content["cortex_protocol"]);
                list[t].set("cortex_host", content["cortex_host"]);
                list[t].set("cortex_port", content["cortex_port"]);
                list[t].set("max_jobs", content["cortex_jobs_max"]);
                list[t].set("form.max_jobs", content["cortex_jobs_max"]);
                list[t].set("sort_jobs", content["cortex_jobs_sort"]);
                list[t].set("form.sort_jobs", content["cortex_jobs_sort"]);
	    }
			
        }
    
        // Console feedback
        console.log("Cortex settings recovered"); 
 
    })
});

