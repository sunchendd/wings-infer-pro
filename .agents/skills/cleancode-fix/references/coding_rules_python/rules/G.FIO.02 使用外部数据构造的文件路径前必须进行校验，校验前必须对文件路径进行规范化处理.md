# G.FIO.02 使用外部数据构造的文件路径前必须进行校验，校验前必须对文件路径进行规范化处理

- **规则ID**：4c3888c5-cb7c-44e6-b724-8e2f43194a8f
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

使用外部数据构造文件路径时，必须对其合法性进行校验，否则可能会产生路径遍历（Path Traversal）漏洞。文件路径有多种表现形式，如绝对路径、相对路径，路径中可能会包含各种链接、快捷方式、影子文件等，这些都会对文件路径的校验产生影响，所以在文件路径校验前要对文件路径进行规范化处理。

**【正确示例】**

```
##### 场景1：
- 修复示例：对文件路径进行校验

 ```python
 import os


 def path_verify(path, safe_start):
     # 校验函数里是对参数进行realpath方法生成真实路径，并对生成的路径进行预期校验，预期校验是根据业务的角度去校验的，常见的预期校验方法如：startswith、正则等。
     # 注：os.path.exists不属于预期校验
     real_path = os.path.realpath(path)  # 清理告警第一步：用realpath方法
     if real_path.startswith(safe_start):  # 清理告警第二步：预期校验
         return real_path


 path = input()  # 污染源，例如input、sys.argv、os.environ 等
 safe_start = "/usr/test"
 try:
     # 对文件路径进行校验
     verified_path = path_verify(path, safe_start)  # 污染源数据经过特定函数名的校验函数，对污染源数据进行校验，污染源数据即不可信数据变为可信数据
     if verified_path:
         os.removedirs(verified_path)  # 符合
 except Exception as ex:
     print(ex)
  ```

```
**【错误示例】**

```
##### 场景1：
- 错误示例：未对文件路径进行规范化处理

 ```python
 import os


 path = input()
 try:
     # 未对文件路径进行规范化处理
     os.removedirs(os.path.abspath(path))  # 不符合
 except Exception as ex:
     print(ex)
  ```

```
**【修复建议】**

先用os.path.realpath获取真实路径，再通过对生成的真实路径做预期判断，预期校验的方式有很多种，最终的校验效果只要确保真实路径是在安全目录下即可。例如可以用startswith或反过来判断real_path不在哪些路径下等方式，判断该真实路径在能够安全路径下（但注意不能使用endswith、os.path.exists、os.path.isdir等属于无效预期判断的方式进行预期判断）。



说明：os.path.realpath()方法标准化的文件路径，文件目录会缺少末尾的文件路径分隔符，进行文件路径校验时，要考虑该场景的影响，防止文件路径校验出现与预期不符的结果。
