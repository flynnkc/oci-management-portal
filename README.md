# OCI Management Dashboard

## Installation

### 1. Creat Identity Domain Confidential Application

1. Integrated Applications and _Add application_. Select _Confidential Application_.
    - Give a name and _Next_
    - Resource server _Primary Audience_
    - _Configure this application as a client now_
    - _Client Credentials_ and _Authorization Code_ grants
    - _Redirect URL_ as callback URL
    - Client type _Confidential_
    - Client IP address
    - Token issuance policy
    - Next and Activate

## Configuration

The application uses environment variables to get configurations:

- OCIDOMAIN_AUTH_TYPE

    Authentication type for application to use for connecting to OCI:

  - profile
  - instance_principal
  - delegation_token
  - workload_principal

- OCIDOMAIN_IDM_ENDPOINT

    The OIDC provider endpoint _(ex. `https://idcs-xyz.identity.oraclecloud.com`)_

- OCIDOMAIN_CLIENT_ID

    The OIDC provider client ID _(ex. `12345`)_

- OCIDOMAIN_CLIENT_SECRET

    The OIDC provider secret _(ex. `abcdef`)_

- OCIDOMAIN_APP_URI

    URI to reach application _(ex. `https://foo.bar:4431`)_

- OCIDOMAIN_TAG_NAMESPACE

    Tag namespace for Search _(ex. `Team-A`)_

- OCIDOMAIN_TAG_KEY

    Tag key for Search _(ex. `User`)_

- OCIDOMAIN_FILTER_NAMESPACE

    Tag namespace for Filter _(ex. `Admin`)_

- OCIDOMAIN_FILTER_KEY

    Tag key for Filter _(ex. `Expires`)_

- OCIDOMAIN_PROFILE

    If using Profile authentication, profile to use in Search and Delete _(Default: DEFAULT)_

- OCIDOMAIN_LOCATION

    If using Profile authentication, OCI config file location _(Default: ~/.oci/config)_

## Deploy

### Standalone

1. Choose a domain name (ex. dashboard.example.com)
2. Create the **gunicorn** user
3. Create Python virutal environment

    ```bash
        mkdir venv && python3.11 -m venv flaskapp
    ```

4. [Install Certbot](https://certbot.eff.org/instructions)
5. Set SELinux to permissive

    Temporarily (will revert on restart):

    ```bash
    sudo setenforce 0
    ```

    Permanently:

    In **/etc/selinux/config**, set **SELINUX** to _permissive_

    ```bash
        SELINUX=permissive
        SELINUXTYPE=targeted
    ```

6. Firewalld open 80, 443

    ```bash
    sudo firewall-cmd --add-service=http --add-service=https --permanent --zone=public
    sudo firewall-cmd --reload
    ```

7. Systemd

    - Socket

        Create the file **/etc/systemd/system/gunicorn.socket** and write the following:

        ```bash
        [Unit]
        Description=gunicorn socket

        [Socket]
        ListenStream=/run/gunicorn/gunicorn.sock
        SocketUser=nginx
        SocketGroup=nginx
        SocketMode=0660

        [Install]
        WantedBy=sockets.target
        ```

    - Service

        Create the file **/etc/systemd/system/gunicorn.service** and write the following:

        ```bash
            [Unit]
            Description=gunicorn daemon
            Requires=gunicorn.socket
            After=network.target

            [Service]
            Type=notify
            NotifyAccess=main
            User=gunicorn
            Group=gunicorn
            RuntimeDirectory=gunicorn
            WorkingDirectory=/home/gunicorn/oci-management-portal/src/app
            ExecStart=/home/gunicorn/venv/flaskapp/bin/gunicorn \
                    -c gunicorn.conf wsgi:app
            ExecReload=/bin/kill -s HUP $MAINPID
            KillMode=mixed
            TimeoutStopSec=5
            PrivateTmp=true
            ProtectSystem=strict

            [Install]
            WantedBy=multi-user.target
        ```

        Set **/etc/systemd/system/gunicorn.service.d/override.conf**

        ```bash
            sudo systemctl edit gunicorn
        ```

        ```bash
            [Service]
            Environment="OCIDOMAIN_CLIENT_ID=abcd"
            Environment="OCIDOMAIN_CLIENT_SECRET=efgh"
            Environment="OCIDOMAIN_IDM_ENDPOINT=https://idcs-ijkl.identity.oraclecloud.com:443"
            Environment="OCIDOMAIN_APP_URI=http://dashboard.example.com:5000"
            Environment="OCIDOMAIN_TAG_NAMESPACE='A-Team'"
            Environment="OCIDOMAIN_TAG_KEY='Creator'"
            Environment="OCIDOMAIN_AUTH_TYPE=instance_principal"
            Environment="OCIDOMAIN_FILTER_TAG=Expires"
        ```

        Once the above is done:

        ```bash
            sudo systemctl enable --now gunicorn
        ```

8. Nginx

    Create **/etc/nginx/conf.d/dashboard.conf** and populate with the follwing:

    ```nginx
            server {
            listen 80;
            server_name dashboard.example.com;

            location / {
                include proxy_params;
                proxy_pass http://unix:/run/gunicorn/gunicorn.sock;
                }
        }
    ```

    Once the above is done:

    ```bash
        sudo systemctl enable --now nginx
    ```

9. Get Certbot to issue TLS Certificate

    ```bash
        sudo certbot --nginx
    ```
