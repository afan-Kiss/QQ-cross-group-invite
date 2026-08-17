export namespace main {
	
	export class AppInfo {
	    appVersion: string;
	    wailsVersion: string;
	    goVersion: string;
	    frontendVersion: string;
	    pythonServiceVersion: string;
	    logsDir: string;
	
	    static createFrom(source: any = {}) {
	        return new AppInfo(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.appVersion = source["appVersion"];
	        this.wailsVersion = source["wailsVersion"];
	        this.goVersion = source["goVersion"];
	        this.frontendVersion = source["frontendVersion"];
	        this.pythonServiceVersion = source["pythonServiceVersion"];
	        this.logsDir = source["logsDir"];
	    }
	}
	export class DiagnosticItem {
	    label: string;
	    value: string;
	    ok: boolean;
	
	    static createFrom(source: any = {}) {
	        return new DiagnosticItem(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.label = source["label"];
	        this.value = source["value"];
	        this.ok = source["ok"];
	    }
	}

}

export namespace service {
	
	export class BootstrapStatus {
	    localService: string;
	    message: string;
	    startedByUs: boolean;
	    napcatOnline: boolean;
	    napcatMessage: string;
	    appSession: string;
	
	    static createFrom(source: any = {}) {
	        return new BootstrapStatus(source);
	    }
	
	    constructor(source: any = {}) {
	        if ('string' === typeof source) source = JSON.parse(source);
	        this.localService = source["localService"];
	        this.message = source["message"];
	        this.startedByUs = source["startedByUs"];
	        this.napcatOnline = source["napcatOnline"];
	        this.napcatMessage = source["napcatMessage"];
	        this.appSession = source["appSession"];
	    }
	}

}

