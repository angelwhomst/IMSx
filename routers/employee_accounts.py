from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from datetime import datetime
import database
from routers.auth import get_current_active_user, role_required, get_password_hash

router = APIRouter()

# pydantic model for crud for users
class UserCreate(BaseModel):
    firstName: str
    lastName: str
    username: str
    password: str
    # userRole: str
    # createdAt: datetime
    # updatedAt: datetime

class UserUpdate(BaseModel):
    firstName: str | None = None
    lastName: str | None = None
    password: str | None = None


# admin: create a new employee acc
@router.post('/create', dependencies=[Depends(role_required(["admin"]))])
async def create_user(user: UserCreate):
    hashed_password = get_password_hash(user.password)
    conn = await database.get_db_connection()
    cursor =await conn.cursor()
    try:
        await cursor.execute('''insert into Users (firstName, lastName, username, userPassword, userRole)
                             values (?, ?, ?, ?, 'employee')''',
                             (user.firstName,
                              user.lastName,
                              user.username,
                              hashed_password
                              ))
        await conn.commit()
    finally:
        await cursor.close()
        await conn.close()
    return {'message': 'User created successfully!'}

# admin: fetch all employee accts
@router.get('/list-employee-accounts', dependencies=[Depends(role_required(['admin']))])
async def list_users():
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    await cursor.execute('''select userID, firstName, lastName, username, userRole, createdAt, updatedAt
from users
where isDisabled = 0 ''')
    users = await cursor.fetchall()
    await conn.close()
    return [{"userID": u[0], "firstName": u[1], "lastName": u[2], 
             "username": u[3], "userRole": u[4], "createdAt": u[5], "updatedAt": u[6]}
             for u in users]

# admin: update an employee acc
@router.put("/update/{user_id}", dependencies=[Depends(role_required(['admin']))])
async def update_user(user_id: int, user: UserUpdate):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    updates = []
    values = []

    if user.firstName:
        updates.append("firstName = ?")
        values.append(user.firstName)
    if user.lastName:
        updates.append("lastName = ?")
        values.append(user.lastName)
    if user.password:
        hashed_password = get_password_hash(user.password)
        updates.append("userPassword = ?")
        values.append(hashed_password)
    updates.append("updatedAt = ?")
    values.append(datetime.utcnow())
    
    values.append(user_id)
    if updates:
        try: 
            await cursor.execute(f'''update Users set {', '.join(updates)} 
                                 where userID =? and isDisabled=0''', (*values,))
            await conn.commit()
        finally:
            await cursor.close()
            await conn.close()
        return {'message': 'user updated successfully'}
    return {'message': 'no fields to update'}

# admin: delete an employee acc
@router.delete('/delete/{user_id}', dependencies=[Depends(role_required(['admin']))])
async def delete_user(user_id: int):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    try:
        await cursor.execute('''update Users set
                             isDisabled = 1
                             where userID = ?''',  (user_id,))
        await conn.commit()
    finally:
        await cursor.close()
        await conn.close()
    return{'message': 'User deleted successfully'}


# employee: update tjeir own acc details
@router.put('self-update', dependencies=[Depends(role_required(['employee']))])
async def update_self(user: UserUpdate, current_user=Depends(get_current_active_user)):
    conn = await database.get_db_connection()
    cursor = await conn.cursor()
    updates = []
    values = []

    if user.firstName:
        updates.append("firstName = ?")
        values.append(user.firstName)
    if user.lastName:
        updates.append("lastName = ?")
        values.append(user.lastName)
    if user.password:
        hashed_password = get_password_hash(user.password)
        updates.append("userPassword = ?")
        values.append(hashed_password)
    updates.append('updatedAt = ?')
    values.append(datetime.utcnow())

    values.append(current_user.username)

    if updates:
        try:
            await cursor.execute(f'''update users set {', '.join(updates)}
                                  where username =? and isDisabled =0''',(*values,))
            await conn.commit()
        finally:
            await cursor.close()
            await conn.close()
        return{'message': 'Your account details have been updated!'
               }
    return{'message': 'No fields to update'}
