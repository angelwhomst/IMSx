from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import database

SECRET_KEY = "15882913506880857248f72d1dbc38dd7d2f8f352786563ef5f23dc60987c632"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str or None = None


class User(BaseModel):
    username: str
    firstName: str
    lastName: str
    userRole: str
    disabled: bool or None = None


class UserInDB(User):
    userID: int
    hashed_password: str
    

# set passowrd hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

async def get_user_from_db(username: str):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute('''SELECT userID, username, firstName, lastName, userPassword, userRole, isDisabled 
                            FROM users WHERE username = ?''', (username,))
    user_row = await cursor.fetchone()
    await conn.close()
    
    if user_row:
        return UserInDB(
            userID=user_row[0],
            username=user_row[1],
            firstName=user_row[2],
            lastName=user_row[3],
            hashed_password=user_row[4],
            userRole=user_row[5],
            disabled=user_row[6] == 1
        )
    return None

# create the admin user if not already exists
async def create_admin_user():
    admin_user = await get_user_from_db('admin')
    if not admin_user:
        hashed_password = get_password_hash('admin123')
        conn = await database.get_db_connection()
        cursor = await conn.cursor()
        try:
            await cursor.execute('''INSERT INTO users (firstName, lastName, username, userPassword, userRole) 
                                    VALUES (?, ?, ?, ?, ?)''',
                                 ('Admin', 'User', 'admin', hashed_password, 'admin'))
            await conn.commit()
        finally:
            await cursor.close()  
            await conn.close()  

# call the functio nto create admin user on app startup
@router.on_event('startup')
async def on_startup():
    await create_admin_user()

# helper function to verify pw
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

# authenticate user based on usernamea nd pw
async def authenticate_user(username: str, password: str):
    user = await get_user_from_db(username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None

    return user

# creates access token (JWT)
def create_access_token(data: dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


#  gets the current user from DB based on JWT token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credential_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credential_exception

    user = await get_user_from_db(token_data.username)
    if user is None:
        raise credential_exception

    return user

# get the current acitve user
async def get_current_active_user(current_user: UserInDB = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# role-based restrictions
def role_required(required_roles: list[str]):
    async def role_checker(current_user: UserInDB = Depends(get_current_active_user)):
        if current_user.userRole not in required_roles:
            raise HTTPException(status_code=403, detail="Access denied")
        return current_user
    return role_checker


# route to authenticate user and return JWT token
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Incorrect username or password", 
                            headers={"WWW-Authenticate": "Bearer"})
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.userRole}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}


# endpoint to fetch current user's details
@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user


'''
exampele of route where onyly the admin has acces
'''
@router.get("/admin-only-route", dependencies=[Depends(role_required(["admin"]))])
async def admin_only_route():
    return {"message": "This is restricted to admins only"}
