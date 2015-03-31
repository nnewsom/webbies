class Probe(object):
    def __init__(self,url,code,body):
        self.url = url
        self.code = code
        self.length = len(body)
        self.body = body

    def __str__(self):
        return "{url},{code},{length}".format(
                url=self.url,
                code=self.code,
                length=self.length
                )

    def __hash__(self):
        return hash(
            self.url+
            str(self.code)+
            str(self.length)
            )

    def __eq__(self,other):
        return (self.url,self.code,self.length) == (other.url,other.code,other.length)
