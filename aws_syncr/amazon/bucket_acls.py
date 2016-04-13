def FullControl(grantee):
    return {"Permission": "FULL_CONTROL", "Grantee": grantee}

def Read(grantee):
    return {"Permission": "READ", "Grantee": grantee}

def Write(grantee):
    return {"Permission": "WRITE", "Grantee": grantee}

def ReadACP(grantee):
    return {"Permission": "READ_ACP", "Grantee": grantee}

def WriteACP(grantee):
    return {"Permission": "WRITE_ACP", "Grantee": grantee}

AuthenticatedUsersGroup = {"URI": "http://acs.amazonaws.com/groups/global/AuthenticatedUsers", "Type": "Group"}

AllUsersGroup = {"URI": "http://acs.amazonaws.com/groups/global/AllUsers", "Type": "Group"}

LogDeliveryGroup = {"URI": "http://acs.amazonaws.com/groups/s3/LogDelivery", "Type": "Group"}

EC2Group = {'Type': 'CanonicalUser', 'DisplayName': 'za-team', 'ID': '6aa5a366c34c1cbe25dc49211496e913e0351eb0e8c37aa3477e40942ec6b97c'}

