# 🌊 Ocean CTF
一个动态flag练习靶场平台

## ✅ TODO

- [x] 容器管理 
- [x] 题库管理
- [x] 动态flag
- [x] 作弊检测
- [x] 公告通知
- [x] 动态启动题库
- [x] 题库隔离
- [x] 公告通知
- [x] 排行榜
- [x] 快速部署
- [ ] 大屏展示
- [x] 权限分离
- [x] 一键部署
- [ ] 多端口开放
- [ ] fix bug



## 🚀 预览

线上地址 http://94.74.111.52/
管理后台 http://94.74.111.52/manager  访客账号  test/test  
默认超级管理员账号 admin/admin

## 🌍 使用

如何添加容器主机？
#### 远程
1. 启用docker api   —H tcp://0.0.0.0:2375 （一定要添加防火墙规则仅允许指定ip访问）

2. curl 127.0.0.1:2375/_ping    输出OK 说明启用成功

3. 添加主机ip 一栏是web 应用的入口如果是公网云请填写公网地址、如果是虚拟机请填写与物理机同一网段地址，docker API 一栏可以填写127.0.0.1:2375 这是由于部分服务器仅仅只对本地地址开放了2375端口，而如果是docker-compose 部署则无法使用127.0.0.1 可以使用docker的172网段代替。

#### 本地
docker api  unix:///var/run/docker.sock
   



## 📖 安装步骤

##### clone

```
git clone --recursive https://github.com/tongchengbin/ocean_ctf.git /opt/ocean_ctf
```

### docker方式

> docker 编排会引用.env文件中的环境变量

##### 前置环境

```
docker、docker-compose
```

##### compose编排
```
cd /opt/ocean_ctf
docker-compose up -d
```


## ❗ 常见问题&注意事项



## 📃 题库

>  题库仓库：[GitHub - tongchengbin/ctfdb: ctf 题库](https://github.com/tongchengbin/ctfdb)

## 💻 题库格式说明
> TODO



## 开发

  后台管理源码：https://github.com/tongchengbin/ocean_manager
## 其他截图

- ![](./doc/image/6.png)

- 容器主机详情

  ​	![](./doc/image/7.png)

- 编译镜像

  ![](./doc/image/9.png)

- 编译进度

  ![](./doc/image/编译进度.png)

- 镜像列表

  ![](./doc/image/8.png)

- 添加动态题库

  ![](./doc/image/添加动态题库.png)

- 首页

  ![](./doc/image/首页.png)

* 启动容器

  ![](./doc/image/启动容器.png)

- 靶场

  ![]()![动态靶场](./doc/image/动态靶场.png) 
  
- 管理后台

  ![](./doc/image/1.png)

  ![]()![2](./doc/image/2.png)

  ![](./doc/image/3.png)

  ![](./doc/image/4.png)

  ![](./doc/image/5.png)
