from .common import random_str
from rancher import ApiError
from .conftest import wait_until
import time


def test_multiclusterapp_create_no_roles(admin_mc, admin_pc, remove_resource,
                                         user_factory):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"
    targets = [{"projectId": admin_pc.project.id}]
    # admin should be able to create without roles
    mcapp1 = client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)

    # user creating mcapp without roles
    # if user has no roles in target, creation must fail
    user = user_factory()
    remove_resource(user)
    mcapp_name = random_str()
    try:
        user.client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets)
    except ApiError as e:
        assert e.error.status == 403
        assert "has no roles in target project" in e.error.message

    # now admin adds user to this project with some role, creation
    # creation of mcapp must work now
    prtb_member = client.create_project_role_template_binding(
        projectId=admin_pc.project.id,
        roleTemplateId="project-member",
        userId=user.user.id)
    remove_resource(prtb_member)
    wait_until(rtb_cb(client, prtb_member))
    mcapp1 = user.client.\
        create_multi_cluster_app(name=mcapp_name,
                                 templateVersionId=temp_ver,
                                 targets=targets)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)


def test_multiclusterapp_create_with_members(admin_mc, admin_pc,
                                             user_factory, remove_resource):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"

    targets = [{"projectId": admin_pc.project.id}]

    user_member = user_factory()
    remove_resource(user_member)
    user_not_member = user_factory()
    remove_resource(user_not_member)
    members = [{"userPrincipalId": "local://"+user_member.user.id,
                "accessType": "read-only"}]

    mcapp1 = client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets,
                                             members=members)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)

    # check who has access to the multiclusterapp
    # admin and user_member should be able to list it
    id = "cattle-global-data:" + mcapp_name
    mcapp = client.by_id_multi_cluster_app(id)
    assert mcapp is not None
    um_client = user_member.client
    mcapp = um_client.by_id_multi_cluster_app(id)
    assert mcapp is not None

    unm_client = user_not_member.client
    try:
        unm_client.by_id_multi_cluster_app(id)
    except ApiError as e:
        assert e.error.status == 403


def test_multiclusterapp_admin_create_with_roles(admin_mc, admin_pc,
                                                 remove_resource):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"
    targets = [{"projectId": admin_pc.project.id}]
    roles = ["cluster-owner", "project-owner"]
    # roles check should be relaxed for admin
    mcapp1 = client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets,
                                             roles=roles)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)


def test_multiclusterapp_user_create_with_roles(admin_mc, admin_pc,
                                                remove_resource,
                                                user_factory):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"
    targets = [{"projectId": admin_pc.project.id}]
    # make regular user cluster-owner and project-owner in the cluster and
    # it's project
    user = user_factory()
    remove_resource(user)
    user_client = user.client
    crtb_owner = client.create_cluster_role_template_binding(
        clusterId="local",
        roleTemplateId="cluster-owner",
        userId=user.user.id)
    remove_resource(crtb_owner)
    wait_until(rtb_cb(client, crtb_owner))
    prtb_owner = client.create_project_role_template_binding(
        projectId=admin_pc.project.id,
        roleTemplateId="project-owner",
        userId=user.user.id)
    remove_resource(prtb_owner)
    wait_until(rtb_cb(client, prtb_owner))
    roles = ["cluster-owner", "project-owner"]
    mcapp1 = user_client.create_multi_cluster_app(name=mcapp_name,
                                                  templateVersionId=temp_ver,
                                                  targets=targets,
                                                  roles=roles)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)

    # try creating as a user who is not cluster-owner,
    # but that is one of the roles listed, must fail
    user_no_roles = user_factory()
    remove_resource(user_no_roles)
    # add user to project as owner but not to cluster
    prtb_owner = client.create_project_role_template_binding(
        projectId=admin_pc.project.id,
        roleTemplateId="project-owner",
        userId=user_no_roles.user.id)
    remove_resource(prtb_owner)

    wait_until(rtb_cb(client, prtb_owner))
    try:
        user_no_roles.client.\
            create_multi_cluster_app(name=random_str(),
                                     templateVersionId=temp_ver,
                                     targets=targets,
                                     roles=roles)
    except ApiError as e:
        assert e.error.status == 403
        assert "does not have following roles in cluster" in e.error.message
        assert "cluster-owner" in e.error.message


def test_multiclusterapp_admin_update_roles(admin_mc, admin_pc,
                                            remove_resource):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"
    targets = [{"projectId": admin_pc.project.id}]
    roles = ["cluster-owner", "project-owner"]
    mcapp1 = client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets,
                                             roles=roles)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)

    # admin doesn't get cluster-member/project-member roles by default
    # but updating the mcapp to add these roles must pass, since global admin
    # should have access to everything and must be excused
    new_roles = ["cluster-owner", "project-owner", "project-member"]
    updated_mcapp = client.update(mcapp1, roles=new_roles)
    wait_for_roles_to_be_updated(admin_mc, updated_mcapp, new_roles)


def test_multiclusterapp_user_update_roles(admin_mc, admin_pc, remove_resource,
                                           user_factory):
    client = admin_mc.client
    mcapp_name = random_str()
    temp_ver = "cattle-global-data:library-wordpress-2.1.10"
    targets = [{"projectId": admin_pc.project.id}]
    # create mcapp as admin, passing project-owner role
    roles = ["project-owner"]
    # add a user as a member with access-type owner
    user = user_factory()
    remove_resource(user)
    members = [{"userPrincipalId": "local://" + user.user.id,
                "accessType": "owner"}]
    mcapp1 = client.create_multi_cluster_app(name=mcapp_name,
                                             templateVersionId=temp_ver,
                                             targets=targets,
                                             roles=roles,
                                             members=members)
    remove_resource(mcapp1)
    wait_for_app(admin_pc, mcapp_name, 60)

    # user wants to update roles to add project-member role
    # but user is not a part of target project, so this must fail
    new_roles = ["project-owner", "project-member"]
    try:
        user.client.update(mcapp1, roles=new_roles)
    except ApiError as e:
        assert e.error.status == 403
        assert "does not have following roles in project" in e.error.message
        assert "project-member" in e.error.message

    # now admin adds this user to project as project-member
    prtb_member = client.create_project_role_template_binding(
        projectId=admin_pc.project.id,
        roleTemplateId="project-member",
        userId=user.user.id)
    remove_resource(prtb_member)
    wait_until(rtb_cb(client, prtb_member))

    # now user should be able to add project-member role
    updated_mcapp = user.client.update(mcapp1, roles=new_roles)
    wait_for_roles_to_be_updated(admin_mc, updated_mcapp, new_roles)


def wait_for_app(admin_pc, name, timeout=60):
    start = time.time()
    interval = 0.5
    client = admin_pc.client
    cluster_id, project_id = admin_pc.project.id.split(':')
    app_name = name+"-"+project_id
    found = False
    while not found:
        if time.time() - start > timeout:
            raise Exception('Timeout waiting for app of multiclusterapp')
        apps = client.list_app(name=app_name)
        if len(apps) > 0:
            found = True
        time.sleep(interval)
        interval *= 2


def wait_for_roles_to_be_updated(admin_mc, mcapp, roles, timeout=60):
    start = time.time()
    interval = 0.5
    found = False
    id = "cattle-global-data:" + mcapp.name
    while not found:
        if time.time() - start > timeout:
            raise Exception('Timeout waiting for update to '
                            'multiclusterapp roles')

        mcapp = admin_mc.client.by_id_multi_cluster_app(id)
        if mcapp is not None and mcapp.roles == roles:
            found = True
        time.sleep(interval)
        interval *= 2


def rtb_cb(client, rtb):
    """Wait for the prtb to have the userId populated"""
    def cb():
        rt = client.reload(rtb)
        return rt.userPrincipalId is not None
    return cb
