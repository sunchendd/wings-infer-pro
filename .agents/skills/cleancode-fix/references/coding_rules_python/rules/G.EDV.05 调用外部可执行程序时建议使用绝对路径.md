# G.EDV.05 调用外部可执行程序时建议使用绝对路径

- **规则ID**：ba1a9e64-cc76-4a0a-be4b-f50928163580
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

在POSIX环境中，调用可执行程序依赖于PATH环境变量，如果攻击者能够调整PATH变量的内容或操纵文件系统，则用户可能会调用到虚假的可执行文件。该可执行文件将以创建Python进程的用户权限（可能是ROOT用户）来调用。因此建议以绝对路径调用可执行程序。

**【正确示例】**

```
import subprocess


subprocess.run(['/usr/bin/gcc', '--version'], shell=False)

```
**【错误示例】**

```
import subprocess


subprocess.run(['gcc', '--version'], shell=False)

```
**【修复建议】**

以绝对路径调用可执行程序。
