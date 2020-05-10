require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {

    // Console feedback
    console.log("Get TheHive settings"); 
 
    // Create a service and request a refresh for analyzers
    var service = mvc.createService();
    service.get('TA_thehive_cortex_settings/thehive', "", function(err, response) {
 
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
                list[t].set("thehive_protocol", content["thehive_protocol"]);
                list[t].set("thehive_host", content["thehive_host"]);
                list[t].set("thehive_port", content["thehive_port"]);
                list[t].set("max_cases", content["thehive_cases_max"]);
                list[t].set("form.max_cases", content["thehive_cases_max"]);
                list[t].set("sort_cases", content["thehive_cases_sort"]);
                list[t].set("form.sort_cases", content["thehive_cases_sort"]);
	    }
			
        }
    
        // Console feedback
        console.log("TheHive settings recovered"); 
 
    })
});

