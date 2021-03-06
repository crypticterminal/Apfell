from app import apfell, db_objects
from sanic.response import json
from app.database_models.model import Callback, Operator, Payload
from sanic import response
from datetime import datetime
from sanic_jwt.decorators import protected, inject_user


@apfell.route(apfell.config['API_BASE'] + "/callbacks/", methods=['GET'])
@inject_user()
@protected()
async def get_all_callbacks(request, user):
    callbacks = Callback.select()
    return json([c.to_json() for c in callbacks])


# this one is specifically not @protect or @inject_user because our callback needs to be able to access this
#   and we don't know when the callback will actually happen, so we don't want the JWT to be timed out
@apfell.route(apfell.config['API_BASE'] + "/callbacks/", methods=['POST'])
async def create_callback(request):
    data = request.json
    #print(data)
    if not 'user' in data:
        return json({'status': 'error',
                     'error': 'User required'})
    if not 'host' in data:
        return json({'status': 'error',
                     'error': 'Host required'})
    if not 'pid' in data:
        return json({'status': 'error',
                     'error': 'PID required'})
    if not 'ip' in data:
        return json({'status': 'error',
                     'error': 'IP required'})
    if not 'uuid' in data:
        return json({'status': 'error',
                     'error': 'uuid required'})
    # Get the corresponding Payload object based on the uuid
    try:
        payload = await db_objects.get(Payload, uuid=data['uuid'])
        # now that we have a uuid and payload, we should check if there's a matching parent callback
        if payload.pcallback:
            pcallback = await db_objects.get(Callback, id=payload.pcallback)
        else:
            pcallback = None
    except Exception as e:
        print(e)
        return json({'status': 'error',
                     'error': 'Failed to find payload',
                     'msg': str(e)})
    try:
        cal = await db_objects.create(Callback, user=data['user'], host=data['host'], pid=data['pid'],
                                      ip=data['ip'], description=payload.tag, operator=payload.operator,
                                      registered_payload=payload, pcallback=pcallback, operation=payload.operation)
    except Exception as e:
        print(e)
        return json({'status': 'error',
                     'error': 'Failed to create callback',
                     'msg': str(e)})
    cal_json = cal.to_json()
    status = {'status': 'success'}
    return response.json({**status, **cal_json}, status=201)


@apfell.route(apfell.config['API_BASE'] + "/callbacks/<id:int>", methods=['GET'])
@inject_user()
@protected()
async def get_one_callback(request, id, user):
    try:
        cal = await db_objects.get(Callback, id=id)
        return json(cal)
    except Exception as e:
        print(e)
        return json({'status': 'error', 'error': 'failed to get callback'}, 404)


@apfell.route(apfell.config['API_BASE'] + "/callbacks/<id:int>", methods=['PUT'])
@inject_user()
@protected()
async def update_callback(request, id, user):
    data = request.json
    try:
        cal = await db_objects.get(Callback, id=id)
        if 'description' in data:
            cal.description = data['description']
        if 'active' in data:
            if data['active'] == 'true':
                cal.active = True
            elif data['active'] == 'false':
                cal.active = False
        await db_objects.update(cal)
        success = {'status': 'success'}
        updated_cal = cal.to_json()
        return json(**success, **updated_cal)
    except:
        return json({'status': 'error', 'error': 'failed to update callback'})


@apfell.route(apfell.config['API_BASE'] + "/callbacks/<id:int>", methods=['DELETE'])
@inject_user()
@protected()
async def remove_callback(request, id, user):
    try:
        cal = await db_objects.get(Callback, id=id)
        cal.active = False
        await db_objects.update(cal)
        success = {'status': 'success'}
        deleted_cal = cal.to_json()
        return json({**success, **deleted_cal})
    except:
        return json({'status': 'error', 'error': "failed to delete callback"})


@apfell.route(apfell.config['API_BASE'] + "/callbacks/update_active", methods=['GET'])
@inject_user()
@protected()
async def update_active_callbacks(request, user):
    # Add this as a 'Task' in Sanic's loop so it repeatedly get calls to update this behind the scenes
    #   It can also be done manually at any time via this GET request to update all callback statuses
    try:
        all_callbacks = await db_objects.get(Callback, active=True)
        # if a callback is more than 3x late for a checkin, it's considered inactive
        #   if/when it does finally callback, its status will be updated to active again
        #   There's no need to look at callbacks already set to 'inactive'
        # TODO finish this part by adding a task to periodically do this to the event loop
        for c in all_callbacks:
            if (c.callback_interval * 3 + c.last_checkin) > datetime.now():
                c.active = False
                try:
                    await db_objects.update(c)
                except Exception as e:
                    print("Failed to update callback to inactive")
                    print(e)
    except Exception as e:
        print(e)
        return json({'status': 'error', 'error': str(e)})
