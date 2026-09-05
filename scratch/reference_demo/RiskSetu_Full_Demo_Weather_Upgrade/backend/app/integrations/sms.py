"""No messages sent until an approved gateway is integrated."""
class SMSProvider:
    def send(self, phone, message):
        return {'sent':False,'status':'NOT_CONFIGURED','message':'Approved SMS gateway required'}
