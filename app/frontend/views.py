import random
import string
from datetime import datetime,timedelta

import docker
from docker import errors as docker_error
from flask import Blueprint, jsonify, render_template, request, make_response, g, redirect, send_from_directory
from sqlalchemy import func, desc
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.auth.acls import auth_cookie
from app.lib.tools import get_ip
from app.lib.utils.authlib import create_token
from app.models.admin import Notice
from app.models.ctf import ImageResource, ContainerResource, Answer, QuestionFile, Question
from app.models.user import User
from app.tasks.ctf import finish_container

bp = Blueprint("view", __name__, url_prefix='')


@bp.route('/manager', methods=['get'])
def redirect_manager():
    """
    开发模式下 管理页面的跳转
    @return:
    """

    return redirect('/manager/index.html')


@bp.route('/manager/<path:filename>')
def manager_static(filename):
    # 注册静态文件
    manager_folder = "./dist"
    print(filename)
    return send_from_directory(manager_folder, filename, cache_timeout=500)


@bp.route('/upload/<path:filename>')
def send_upload_file(filename):
    cache_timeout = None
    manager_folder = 'upload'
    return send_from_directory(manager_folder, filename, cache_timeout=cache_timeout)


def generate_flag():
    """
        生成flag
        return generate flag
    """
    rd_str = ''.join(random.sample(string.ascii_letters + string.digits, 32))
    return "flag{ocean%s}" % rd_str


@bp.route('/', methods=['get'])
@auth_cookie
def index():
    """
        :return :首页 后端渲染
    """
    subject = request.args.get('subject')
    subjects = ("Web", "Crypto", "Pwn", "Iot", "Misc")
    query = db.session.query(Question)
    if subject:
        query = query.filter(Question.type == subject.lower())
    solved_qid = []
    if g.user:
        # 我已解决的题目
        solved_question = db.session.query(Answer.question_id).filter(Answer.user_id == g.user.id,
                                                                      Answer.status == 1).all()
        solved_qid = [i[0] for i in solved_question]
    data = []
    links = {}
    if g.user:
        # 获取镜像资源
        containers = db.session.query(ContainerResource, ImageResource.question_id) \
            .join(ImageResource, ImageResource.id == ContainerResource.image_resource_id
                  ) \
            .join(User, User.id == ContainerResource.user_id).order_by(desc(ContainerResource.id)).all()
        # 获取用户容器
        for c in containers:
            container, question_id = c
            links[question_id] = ["%s:%s" % (container.addr, container.container_port)]
    # 统计每个题目解决人数

    solved_query = db.session.query(Answer.question_id, func.count(Answer.id)).filter(Answer.status == 1).group_by(
        Answer.question_id)
    solved_state = {}
    for qid, cnt in solved_query:
        solved_state[qid] = cnt
    for item in query:
        data.append({
            "active_flag": item.active_flag,
            "id": item.id,
            "links": links.get(item.id, []),
            "type": item.type,
            "desc": item.desc,
            "name": item.name,
            "integral": item.integral,
            "solved": solved_state.get(item.id, 0),
            "date_created": item.date_created.strftime("%y-%m-%d"),
            "has_solved": True if item.id in solved_qid else False
        })
    # 公告
    notices = []
    notice_query = db.session.query(Notice).all()
    for item in notice_query:
        notices.append({
            "id": item.id,
            "content": item.content,
            "date_create": item.date_created.strftime("%Y-%m-%d %H:%M")
        })
    response = make_response(render_template('index.html', user=g.user, challenges=data,
                                             subjects=subjects,
                                             subject=subject,
                                             notices=notices))
    if not g.user:
        response.delete_cookie('token')
    return response


@bp.route('/login', methods=['get', 'post'])
def login():
    """
    用户登录
    """
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        if not all([username, password]):
            return render_template('login.html', error="用户名或密码不允许为空")
        user = db.session.query(User).filter(User.username == username).one_or_none()
        if user and check_password_hash(user.password, password):
            token = create_token()
            user.token = token
            db.session.commit()
            response = make_response(redirect('/'))
            response.set_cookie("token", token)
            return response
        else:
            return render_template('login.html', error="用户名或密码不允许为空")
    return render_template('login.html')


@bp.route('/register', methods=['get', 'post'])
def register():
    """
    用户注册
    """
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")
        password2 = request.form.get("password2")
        if not all([username, password, password2]):
            return render_template('login.html', error="用户名或密码不允许为空")
        user = db.session.query(User).filter(User.username == username).one_or_none()
        if user:
            return render_template('register.html', error="该用户名已注册")
        if password2 != password:
            return render_template('register.html', error="两次输入的密码不匹配")
        token = create_token()
        user = User(username=username, password=generate_password_hash(password), active=True, token=token)
        db.session.add(user)
        db.session.commit()
        response = make_response(redirect('/'))
        response.set_cookie("token", token)
        return response
    return render_template('register.html')


@bp.route('/logout', methods=['get'])
@auth_cookie
def logout():
    """
    用户登出
    """
    response = redirect('/')
    response.delete_cookie('token')
    return response


@bp.route('/challenge/<int:question>/detail', methods=['get'])
@auth_cookie
def challenge_detail(question):
    """
        题目详情 包括已解决的用户情况  点赞情况
    :param question:
    :return:
    """
    instance = db.session.query(Question).get(question)
    if g.user and instance.active_flag:
        # 获取镜像资源
        container = db.session.query(ContainerResource) \
            .join(ImageResource, ImageResource.id == ContainerResource.image_resource_id
                  ) \
            .join(User, User.id == ContainerResource.user_id).filter(ImageResource.question_id == instance.id, \
                                                                     User.id == g.user.id) \
            .order_by(ContainerResource.id.desc()).first()
        # 获取用户容器
        if container:
            links = ["%s:%s" % (container.addr, container.container_port)]
        else:
            links = []
    else:
        links = []
    # 附件
    question_file = db.session.query(QuestionFile).filter(QuestionFile.question_id == instance.id).all()
    data = {
        "links": links,
        "id": instance.id,
        "name": instance.name,
        "question_file": question_file,
        "desc": instance.desc,
        "active_flag": instance.active_flag,
        "type": instance.type,
        "solved": db.session.query(Answer).filter(Answer.question_id == instance.id,
                                                  Answer.status == Answer.status_ok).count(),
        "date_created": instance.date_created.strftime("%y-%m-%d")
    }
    return render_template('challengeDetail.html', item=data)


@bp.route('/challenge/<int:question>/start', methods=['POST'])
@auth_cookie
def question_start(question):
    """
        创建一个题目容器
    :param question:
    :return:
    """
    if not g.user:
        return make_response(jsonify({"msg": "请先登陆"}), 401)
    user = g.user
    instance = db.session.query(Question).get(question)
    if not instance.active_flag:
        return make_response(jsonify({"msg": "静态题库无需动态生成"}))
    image_resource = db.session.query(ImageResource).filter(ImageResource.question_id == instance.id).one_or_none()
    if not image_resource:
        return make_response(jsonify({"msg": "服务器没有资源"}), 400)
    connect_url = "http://" + image_resource.host.addr
    client = docker.DockerClient(connect_url)
    image = client.images.get(image_resource.image_id)
    # 解析镜像端口
    image_config = image.attrs["ContainerConfig"]
    random_port = ""
    if "ExposedPorts" in image_config:
        port_dict = image.attrs["ContainerConfig"]["ExposedPorts"]
        for docker_port, host_port in port_dict.items():
            # docker_port_int = docker_port.replace("/", "").replace("tcp", "").replace("udp", "")
            random_port = str(random.randint(10000, 65536))
            port_dict[docker_port] = random_port
    else:
        port_dict = {}
    image_name = image.attrs["RepoTags"][0].replace(":", ".")
    container_name = f"{image_name}_{user.id}"
    # 检查docker 是否已存在
    try:
        c = client.containers.get(container_name)
        c.stop()
        c.remove()
    except docker.errors.NotFound:
        pass
    docker_container_response = client.containers.run(image=image.id, name=container_name, ports=port_dict,
                                                      detach=True)
    # 获取创建的容器
    docker_container = client.containers.get(container_name)
    flag = generate_flag()
    command = "/bin/bash /start.sh '{}'".format(flag)
    docker_container.exec_run(cmd=command, detach=True)
    # 创建容器记录
    container = ContainerResource(image_resource_id=image_resource.id, flag=flag)
    container.addr = image_resource.host.ip
    container.container_id = docker_container_response.attrs["Id"]
    container.image_id = image.attrs["Id"]
    container.container_name = container_name
    container.container_status = docker_container_response.attrs["State"]["Status"]
    container.container_port = random_port
    container.user_id = user.id
    # 销毁时间
    container.destroy_time = datetime.now() + timedelta(minutes=10)
    # 创建容器
    db.session.add(container)
    db.session.commit()
    # 创建定时任务  到时间后销毁
    finish_container.apply_async(args=(container.id,),countdown=60*10)
    return jsonify({
        "status": 0
    })


@bp.route('/challenge/<int:question>/destroy', methods=['POST'])
@auth_cookie
def question_destroy(question):
    """
        销毁容器
    :param question:
    :return:
    """
    if not g.user:
        return make_response(jsonify({"msg": "请先登陆"}), 401)
    instance = db.session.query(Question).get(question)
    if not instance.active_flag:
        return make_response(jsonify({"msg": "静态题库无需动态生成"}))
    containers = db.session.query(ContainerResource, ImageResource).join(ImageResource,
                                                                         ImageResource.id == ContainerResource.image_resource_id). \
        filter(ImageResource.question_id == instance.id, ContainerResource.user_id == g.user.id)
    for (container, image_resource) in containers:
        try:
            client = docker.DockerClient("http://{}".format(image_resource.host.addr), timeout=3)
            docker_container = client.containers.get(container.container_id)
            docker_container.kill()
            docker_container.remove()
        except docker_error.DockerException:
            pass
        db.session.delete(container)
    db.session.commit()
    return jsonify({
        "status": 0
    })


@bp.route('/user', methods=['get'])
@auth_cookie
def user_center():
    """
        用户中心 # todo
    """
    return render_template('user.html')


@bp.route('challenge/<int:question>/submit_flag', methods=["post"])
@auth_cookie
def submit_flag(question):
    """
    提交flag
        :param  question: 题目ID
        :data flag: 提交的flag
    """
    ip = get_ip()
    instance = db.session.query(Question).get(question)
    flag = request.get_json().get('flag')
    if not flag:
        return make_response(jsonify({"msg": "flag不允许为空"}), 400)
    if not g.user:
        return make_response(jsonify({"msg": "请登录"}), 401)
    answer = Answer(question_id=instance.id, user_id=g.user.id, flag=flag, ip=ip)
    # 判断是否有正确的提交记录
    is_answer = db.session.query(Answer).filter(Answer.question_id == instance.id, Answer.user_id == g.user.id,
                                                Answer.status == Answer.status_ok).count()

    if instance.active_flag:
        # 获取镜像资源
        container = db.session.query(ContainerResource).join(ImageResource,
                                                             ImageResource.id == ContainerResource.image_resource_id) \
            .filter(ImageResource.question_id == instance.id, ContainerResource.user_id == g.user.id) \
            .order_by(ContainerResource.id.desc()).first()
        if not container:
            answer.status = answer.status_error
            db.session.commit()
            return make_response(jsonify({"msg": "题库无效，请联系管理员或重新生成!"}), 400)
        # 判断是否是作弊
        ok_container = db.session.query(ContainerResource) \
            .join(ImageResource, ContainerResource.image_resource_id == ImageResource.id) \
            .filter(ContainerResource.flag == flag, ImageResource.question_id == instance.id).first()
        if ok_container and ok_container != container:
            # 作弊
            answer.status = answer.status_cheat
            db.session.add(answer)
            db.session.commit()
            return make_response(jsonify({"msg": "请勿作弊"}), 400)

        try:
            client = docker.DockerClient("http://{}".format(container.image_resource.host.addr))
            docker_container = client.containers.get(container.container_id)
        except docker_error.DockerException:
            return make_response(jsonify({"msg": "容器不在线"}), 400)
        if container.flag == flag:
            answer.score = instance.integral
            # 判断是否作弊
            answer.status = answer.status_repeat if is_answer else answer.status_ok
            # 销毁容器
            docker_container.kill()
            docker_container.remove()
            db.session.delete(container)
            db.session.add(answer)
            db.session.commit()
        else:
            answer.status = answer.status_error
            db.session.add(answer)
            db.session.commit()
            return make_response(jsonify({"msg": "Flag错误!"}), 400)
    elif instance.flag == flag:
        answer.score = instance.integral
        answer.status = answer.status_repeat if is_answer else answer.status_ok
        db.session.add(answer)
        db.session.commit()
    else:
        answer.status = answer.status_error
        db.session.add(answer)
        db.session.commit()
        return make_response(jsonify({"msg": "flag错误!"}), 400)
    return jsonify({"status": 0})


@bp.route('notice', methods=['get'])
@auth_cookie
def notice():
    """
        公告中心
    """
    # 公告
    notices = []
    notice_query = db.session.query(Notice).order_by(Notice.id.desc()).all()
    for item in notice_query:
        notices.append({
            "id": item.id,
            "content": item.content,
            "date_created": item.date_created.strftime("%Y-%m-%d %H:%M")
        })
    return render_template('notice.html', notices=notices, user=g.user)


@bp.route('user_rank', methods=['get'])
@auth_cookie
def user_rank():
    """
        公告中心
    """
    # 公告
    cursor = db.session.execute('''select user.id,user.username,user.date_created,
    count(answer.id),
    sum(answer.score) as score,
     max(answer.date_created) as last_ans
     from `user` left join answer 
    on user.id=answer.user_id where answer.`status`=1 group by user.id order by score desc''')
    result = cursor.fetchall()
    data = []
    for rank, item in enumerate(result):
        user_id, username, date_created, solved_cnt, score, last_ans = item
        data.append({
            "rank": rank + 1,
            "id": user_id,
            "username": username,
            "solved_cnt": solved_cnt,
            "date_created": date_created.strftime("%Y-%m-%d %H:%M"),
            "score": score or 0,
            "last_ans": last_ans
        })
    return render_template('user_rank.html', data=data, user=g.user)
