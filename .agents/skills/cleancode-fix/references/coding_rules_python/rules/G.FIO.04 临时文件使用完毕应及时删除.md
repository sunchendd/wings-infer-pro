# G.FIO.04 临时文件使用完毕应及时删除

- **规则ID**：df843ba3-c892-4485-986b-3cd6b9765237
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

在全局可写的目录中创建临时文件，例如，POSIX系统下的/tmp与/var/tmp目录，Windows系统下的 C:\TEMP目录。这类目录中的文件可能会被定期清理，例如，每天晚上或者重启时。然而，如果文件未被安全地创建或者用完后还是可访问的，具备本地文件系统访问权限的攻击者便可以利用共享目录中的文件进行恶意操作。删除已经不再需要的临时文件有助于对文件名和其他资源（如二级存储）进行回收利用。每一个程序在正常运行过程中都有责任确保删除已使用完毕的临时文件。

注意：下面的示例代码已假设文件在创建时指定了合适的访问权限，以遵循[G.FIO.01 在多用户系统中创建文件时应根据需要指定合适的权限]。

**【正确示例】**

```
【正例1】

import tempfile
tmp_file_handle = tempfile.NamedTemporaryFile(delete=True)
try:
   print(tmp_file_handle.name)
   tmp_file_handle.file.write(b"abc")
except Exception as e:
   doing_something()
finally:
   tmp_file_handle.close()
注：上述打开文件的方法已经不提倡使用，此处仅是为了演示，推荐使用 with... as... 语句。

这个正确示例创建临时文件时用到了NamedTemporaryFile ()方法，该方法会新建一个随机的文件名。文件使用try-finally构造块，在finally处手动关闭文件。而不管是否有异常发生，由于在打开文件时用到了delete选项，使得文件在关闭后会被自动删除。

注意：应根据业务实际的场景，选择关闭文件时是采用自动删除文件的操作，还是采用手动显式删除临时文件的操作。

【正例2】手动删除临时创建的文件

import os
diy_file = "diyData.txt"
content = "Data"
try:
   file_handle = open(diy_file, os.O_WRONLY, int("0600", 8))
   try:
       file_handle.write(content)
   except Exception as e:
       doing_something()
   finally:
       file_handle.close()
except Exception as ex:
   print(ex)
# 建议使用with语句实现上述功能
# 结束时，显式的删除它
if os.path.isfile(diy_file):
    os.remove(diy_file)

```
**【错误示例】**

```
import tempfile


filename = tempfile.mktemp()  # 生成的文件名与时间强相关，有可能引起重名风险
tmp_file = open(filename, "w+")

```
**【修复建议】**

临时文件使用完毕应及时删除。
