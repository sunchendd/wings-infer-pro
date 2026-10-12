# G.FIO.03 禁止使用tempfile.mktemp创建临时文件

- **规则ID**：8292d225-18b7-45ea-a965-95e28b525c4f
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

严重

**【描述】**

禁止使用已知有风险的方法tempfile.mktemp创建临时文件。要求使用安全的方法创建临时文件，包括并不限于tempfile模块的mkstemp, mkdtemp, NamedTemporaryFile函数。

**【正确示例】**

```
import os
import shutil
import tempfile
tmp_file_one = tempfile.mkstemp()  # (3, '/tmp/tmpyo8ddjhq') 创建临时文件
tmp_file_two = tempfile.mkdtemp()  # /tmp/tmpf_od5le5 创建临时目录
tmp_file_three = tempfile.NamedTemporaryFile(delete=False)  # <tempfile._TemporaryFileWrapper object at 0x000001E3D182BE88>
if os.path.isfile(tmp_file_one[1]):
    os.close((tmp_file_one[0]))
    os.remove(tmp_file_one[1])
if os.path.isfile(tmp_file_three.name):
    tmp_file_three.close()
    os.remove(tmp_file_three.name)
if os.path.isdir(tmp_file_two):
    os.mkdir(os.path.join(tmp_file_two, '1.txt'))
    shutil.rmtree(tmp_file_two)

```
**【错误示例】**

```
"import tempfile


filename = tempfile.mktemp()  # 生成的文件名与时间强相关，有可能引起重名风险
tmp_file = open(filename, ""w+"")"


```
**【修复建议】**

使用安全的方法创建临时文件，包括但不限于tempfile模块的mkstemp, mkdtemp, NamedTemporaryFile函数。
