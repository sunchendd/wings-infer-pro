# G.EDV.03 避免在命令解析器中使用通配符

- **规则ID**：c044f8bf-36bb-4527-aa94-d703f7179560
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

致命

**【描述】**

通配符是一种特殊语句，主要有星号（*）和问号（？），用来模糊匹配字符串（比如文件名，参数名），Linux系统中许多命令接受通配符，如果攻击者将软链接或者一些特性文件置于给定的路径位置，则可能造成严重后果。

**【正确示例】**

```
import subprocess
import os


subprocess.Popen(['/bin/chmod', '640', '*'], shell=False) # 报错
subprocess.Popen(['/bin/chown', 'user:user', '*'], shell=False) # 报错
os.chown('filename', uid, gid, follow_symlinks=False) # 禁止对软链接对应的目标文件操作

```
**【错误示例】**

```
import subprocess
import os


os.system('/bin/chmod 640 *')
subprocess.Popen('/bin/chown user:user *', shell=True)

```
**【修复建议】**

在日常开发中执行命令时应该尽量避免使用通配符，否则一不小心就可能造成严重后果。
