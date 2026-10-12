# SecPy_VF_Trust_Boundary_Violation

- **规则ID**：d24913e3-df56-4973-b5d2-0f6135c48e19
- **更新时间**：2025-06-05 04:15:01

---

**【问题级别】**

严重

**【描述】**

检测违反信任边界问题，覆盖场景与fortify规则 Trust Boundary Violation 相同

**【正确示例】**

```
import jinja2
import django
def verify(x):
  if x == 'clean data':
      return x.replace('
', '_').replace('\r', '_');
  else:
     return None
def bad():
    a = input()
    b = input()
    verify_a = verify(a)
    verify_b = verify(b)
    # 传入外部数据前先对其校验
    jinja2.Template.render(verify_a, verify_b)

```
**【错误示例】**

```
import jinja2
import django

def bad():
    a = input()
    b = input()
    c = input()
    d = input()
    # POTENTIAL FLAW
    jinja2.Template.render(a, b)
    # POTENTIAL FLAW
    django.views.generic.base.TemplateResponseMixin.render_to_response(a,b,c,d)

```
**【修复建议】**

传入外部数据之前需要对其进行校验
