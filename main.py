from pydoc_data.topics import topics
from urllib import response
from fastapi import Depends, FastAPI, UploadFile, File
from supabase import Client, create_client
from pydantic import BaseModel
import os
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = [
    "http://localhost:4200"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins = origins,
    allow_credentials=True,
    allow_methods = ["*"],
    allow_headers = ["*"]
)

url = "https://jkqqkoenkqqwlzvvybgd.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImprcXFrb2Vua3Fxd2x6dnZ5YmdkIiwicm9sZSI6ImFub24iLCJpYXQiOjE2NjMyNDQ0MDgsImV4cCI6MTk3ODgyMDQwOH0.oXoDke4KpFgnq7NBs5chsqTJkkH4CFRU-RKmrBApQjU"

symbl_id = "7a673750647a647a3063716e7466333876777250487447357466596370696538"
symbl_secret = "3736385a7a4c645475394c4b775a727476456636383267524b43586a2d507158636a5f375a3669794e77334b656a454b4e6d74374d47776a6832616844415152"

supabase: Client = create_client(url, key)

class user(BaseModel):
    email: str
    password: str

#get the file data
@app.get("/get_data")
async def getFileData():
    fileData = supabase.table('file_meta').select('*').execute()
    return fileData

#post method for signup
@app.post("/signup/")
async def userSignUp(user_signup: user):
    user = supabase.auth.sign_up(email=user_signup.email, password=user_signup.password)
    return user

#post method to for login and also generating the symbl token
symblAuthToken = ""
@app.post("/login/")
async def userLogIn(user_login: user):
    user = supabase.auth.sign_in(email=user_login.email, password=user_login.password)
    return user

async def get_token():
    headers = {
        "Content-Type": "application/json"
    }

    request_body = {
        "type" : "application",
        "appId" : symbl_id,
        "appSecret" : symbl_secret
    }

    symbl_url_token = "https://api-labs.symbl.ai/oauth2/token:generate"
    response = requests.post(symbl_url_token, headers=headers, json=request_body)
    obj = response.json()
    symblAuthToken = obj["accessToken"]
    return symblAuthToken


#post method for upload files and insert tha data in the file_meta table
@app.post("/upload")
def upload(file: UploadFile = File(...)):
    try:
        contents = file.file.read()
        with open(file.filename, 'wb') as f:
            f.write(contents)

    except Exception:
        return {"message": "There was an error uploading the file"}
    finally:
        file.file.close()

    my_file = os.path.dirname(os.path.abspath("__file__")) + "\\" + file.filename
    supabase.storage().StorageFileAPI('uploads').upload(path='video/'+file.filename, file=my_file, file_options={"content-type":"video/mp4"}
    )
    
    publicUrl = supabase.storage().StorageFileAPI('uploads').get_public_url('video/'+file.filename.replace(' ','%20'))
    
    data = supabase.table("file_meta").insert({"file_name":file.filename, "file_type": file.content_type, "public_url": publicUrl}).execute()

    return data

#post method for processing video
@app.post("/processVideo/{file_id}")
async def processVideo(file_id: str, accessToken: str = Depends(get_token)):
    #returns an APIResponse Object
    publicUrl = supabase.table("file_meta").select("public_url").eq("id", file_id).execute()
    #taking out just the publicUrl from the APIResponse Object
    obj_publicUrl = publicUrl.data[0]["public_url"]
    symblai_params = {
    "url": obj_publicUrl
    }

    headers = {
    "Authorization": "Bearer " + accessToken,
    "Content-Type": "application/json"
    }

    response = requests.request(
    method="POST", 
    url="https://api.symbl.ai/v1/process/video/url",
    headers=headers,
    json=symblai_params
    )

    obj = response.json()
    conversationId = obj["conversationId"]
    jobId = obj["jobId"]

    supabase.table("file_meta").update({"conversation_id": conversationId, "job_id": jobId}).eq("id", file_id).execute()

    return response.json()

#creating an API to get the status of the job done
@app.get("/checkstatus/{file_id}")
async def checkStatus(file_id: str, accessToken:str = Depends(get_token)):
    jobId = supabase.table("file_meta").select("job_id").eq("id", file_id).execute()
    obj_jobId = jobId.data[0]["job_id"]

    headers = {
    "Authorization": "Bearer " + accessToken,
    "Content-Type": "application/json"
    }

    response = requests.request(
    method="GET", 
    url="https://api.symbl.ai/v1/job/" + obj_jobId,
    headers=headers
    )

    videoStatus = response.json()
    videoStatus = videoStatus["status"]
    supabase.table("file_meta").update({"video_status": videoStatus}).eq("id", file_id).execute()
    return response.json()


#get method to get the messages that is there in the video
@app.get("/messages/")
async def get_messages(file_id: str, accessToken: str = Depends(get_token)):
    conversationId = supabase.table("file_meta").select("conversation_id").eq("id", file_id).execute()
    obj_conversationId = conversationId.data[0]["conversation_id"]

    headers = {
        "Authorization": "Bearer " + accessToken,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    response = requests.request(method="GET", url="https://api.symbl.ai/v1/conversations/"+obj_conversationId+"/messages", headers=headers)

    messages = response.json()
    supabase.table("file_meta").update({"conversation" : messages}).eq("id", file_id).execute()
    return messages

#get questions from the video 
@app.get("/question/")
async def get_question(file_id: str, accessToken:str = Depends(get_token)):
    conversationId = supabase.table("file_meta").select("conversation_id").eq("id", file_id).execute()
    obj_conversationId = conversationId.data[0]["conversation_id"]

    headers = {
        "Authorization": "Bearer " + accessToken,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    response = requests.request(method="GET", url="https://api.symbl.ai/v1/conversations/"+obj_conversationId+"/questions", headers=headers)

    question = response.json()
    supabase.table("file_meta").update({"question": question}).eq("id", file_id).execute()
    return question

#get summary from the video
@app.get("/summary/")
async def get_summary(file_id: str, accessToken: str = Depends(get_token)):
    conversationId = supabase.table("file_meta").select("conversation_id").eq("id", file_id).execute()
    obj_conversationId = conversationId.data[0]["conversation_id"]

    headers = {
        "Authorization" : "Bearer " + accessToken,
        "Accept" : "application/json",
        "Content-Type": "application/json"
    }

    response = requests.request(method="GET", url="https://api.symbl.ai/v1/conversations/"+obj_conversationId+"/summary", headers=headers)

    summary = response.json()
    supabase.table("file_meta").update({"summary": summary}).eq("id", file_id).execute()
    return summary

#get topics from the video
@app.get("/topics/")
async def get_topics(file_id: str, accessToken: str = Depends(get_token)):
    conversationId = supabase.table("file_meta").select("conversation_id").eq("id", file_id).execute()
    obj_conversationId = conversationId.data[0]["conversation_id"]

    headers = {
        "Authorization" : "Bearer " + accessToken,
        "Accept" : "application/json",
        "Content-Type": "application/json"
    }

    response = requests.request(method="GET", url="https://api.symbl.ai/v1/conversations/"+obj_conversationId+"/topics", headers=headers)

    topics = response.json()
    supabase.table("file_meta").update({"topics": topics}).eq("id", file_id).execute()
    return topics

#get analytics of the video
@app.get("/analytics/")
async def get_analytics(file_id: str, accessToken:str = Depends(get_token)):
    conversationId = supabase.table("file_meta").select("conversation_id").eq("id", file_id).execute()
    obj_conversationId = conversationId.data[0]["conversation_id"]

    headers = {
        "Authorization" : "Bearer " + accessToken,
        "Accept" : "application/json",
        "Content-Type": "application/json"
    }

    response = requests.request(method="GET", url="https://api.symbl.ai/v1/conversations/"+obj_conversationId+"/analytics", headers=headers)

    analytics = response.json()
    supabase.table("file_meta").update({"analytics": analytics}).eq("id", file_id).execute()
    return analytics