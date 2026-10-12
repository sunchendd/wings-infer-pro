# SecPy_VF_Server_Side_Template_Injection

- **规则ID**：a98deee0-ce39-4492-a296-5049475680e9
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

严重

**【描述】**

用户控制的数据用作模板引擎的模板，使得攻击者能够访问模板上下文，并在某些情况下在应用程序服务器中注入和运行任意代码。

**【正确示例】**

```
```
# 【正例 1】对外部数据进行校验
def good_case1(request):
    filename = input()
    with open(filename, 'r') as template_file:
        template = template_file.read()
    name = request.GET['name']
    template = verify(template % name)
    t = jinja2.Template(template)
    html = t.render()
    return HttpResponse(html)


def verify(data):
    # 校验逻辑可自定义
    return data


# 【正例 2】使用沙箱环境
def good_case2(request):
    filename = input()
    with open(filename, 'r') as template_file:
        template = template_file.read()
    name = request.GET['name']
    sandbox_env = SandboxedEnvironment(loader=FileSystemLoader('templates'))
    t = sandbox_env.from_string(template % name)
    html = t.render()
    return HttpResponse(html)
```

```
**【错误示例】**

```
```
# 【反例 1】
def jinja_SSTI1(request):
    filename = input()
    # 当模板文件外部可控时存在风险
    with open(filename, 'r') as template_file:
        template = template_file.read()
    name = request.GET['name']
    t = jinja2.Template(template)
    html = t.render(name=name)
    return HttpResponse(html)


# 【反例 2】
def jinja_SSTI2(request):
    filename = input()
    with open(filename, 'r') as template_file:
        template = template_file.read()
    name = request.GET['name']
    # 当模板直接拼接外部输入时存在风险
    t = jinja2.Template(template % name)
    html = t.render()
    return HttpResponse(html)
```

```
**【修复建议】**

禁止用户输入模板代码。如果必须允许用户输入模板代码，则应该使用安全的模板沙箱来限制代码的执行，或联系安全SE评估安全风险，从设计层面解决。
