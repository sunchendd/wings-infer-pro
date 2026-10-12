# SecPy_VF_Open_Redirect

- **规则ID**：8084bc01-22ce-440d-b65e-e9e4d4e06ad6
- **更新时间**：2026-04-07 04:15:01

---

**【问题级别】**

严重

**【描述】**

通过重定向，Web 应用程序能够引导用户访问同一应用程序内的不同网页或访问外部站点。应用程序通常利用重定向来帮助进行站点导航，有时还跟踪用户退出站点的方式。当 Web 应用程序将客户端重定向到攻击者可以控制的任意 URL 时，就会发生 Open redirect 漏洞。攻击者可以利用 Open redirect 漏洞诱骗用户访问某个可信赖站点的 URL，并将他们重定向到恶意站点。攻击者通过对 URL 进行编码，使最终用户很难注意到重定向的恶意目标，即使将这一目标作为 URL 参数传递给可信赖的站点时也会发生这种情况。因此，Open redirect 常被作为钓鱼手段的一种而滥用，攻击者通过这种方式来获取最终用户的敏感数据。

**【正确示例】**

```
```
from django.http import HttpResponse
from django.shortcuts import redirect
import re


def good_case(request):
    url = request.GET.get('url')
    characterPattern = re.compile(r"^(http|https)://w3.huawei.com")
    if characterPattern.search(url):
        return redirect(url)
    else:
        return HttpResponse("URL not safe")
```

```
**【错误示例】**

```
```
from django.shortcuts import redirect


def bad_case(request):
    url = request.GET.get('url')
    return redirect(url)
```

```
**【修复建议】**

涉及重定向操作时，应该避免由外部用户指定跳转地址。

需要由外部用户指定跳转地址时：

1）在同一网站内部跳转时，建议使用相对url地址进行跳转；

2）涉及跨网站跳转时，需要对外部指定的url地址进行白名单限制（包括域名、端口、网络协议等）。
