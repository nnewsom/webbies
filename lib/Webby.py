class Webby(object):
    def __init__(self,ip,hostname,port,ssl):
        self.ip = ip
        self.hostname = hostname
        self.port = port
        self.title = ""
        self.banner = ""
        self.code = 0
        self.forms = False
        self.login = False
        self.ssl = ssl
        self.success= False
        self.redirect_url = ""
        self.last_response = ""
        self.url = ""
        self.error_msg = ""
        self.group = 0

    #ip,hostname,port,protocol,service,banner,notes,priority
    def __str__(self):
        service = "https" if self.ssl else "http"
        login = "login" if self.login else ""
        forms = "forms" if self.forms else ""
        title = '"%s"' % self.title.replace(',','') if self.title else ""
        if self.success:
            notes = " ".join([str(self.code),self.redirect_url if self.redirect_url else self.url,title,forms,login]).rstrip(' ')
        else:
            notes = """Error: {webby.error_msg}""".format(webby=self)
        csv = """{webby.ip},{webby.hostname},{webby.port},tcp,{service},{webby.banner},{notes},{webby.group}""".format(webby=self,service=service,notes=notes)
        return csv

    def __hash__(self):
        return hash((self.ip,self.hostname,self.port,self.ssl))

    def __eq__(self,other):
        return (self.ip,self.hostname,self.port,self.ssl) == (other.ip,other.hostname,other.port,self.ssl)

    def base_url(self):
        return "{scheme}://{host}:{port}/".format(
                    scheme="https" if self.ssl else "http",
                    host=self.hostname if self.hostname else self.ip,
                    port = self.port
                    )
