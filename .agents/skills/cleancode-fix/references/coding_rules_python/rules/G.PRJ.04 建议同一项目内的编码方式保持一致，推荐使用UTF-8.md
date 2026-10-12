# G.PRJ.04 建议同一项目内的编码方式保持一致，推荐使用UTF-8

- **规则ID**：a40fb6f7-5990-4e86-b9a3-a3853fab4a18
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

Python3默认使用UTF-8编码，使用其它的编码（如`latin-1`，`gbk`等等）可能在使用默认解码的程序解码时出现解码失败。

建议同一项目内的编码方式保持一致。推荐使用默认的UTF-8，如果使用UTF-8编码可以省略不写编码方式。

**【正确示例】**

```
##### 场景1：编码申明
- 修复示例：使用utf-8编码申明
```python
#!/usr/local/bin/python
# coding: utf-8
import os
import sys
...
```
- 修复示例：默认不写编码方式
```python
#!/usr/bin/python
import os
import sys
...
```
##### 场景2：文件实际编码和申明编码不符
- 修复示例：

```
**【错误示例】**

```
##### 场景1：编码申明
- 错误示例：`# latin-1`编码格式错误
```python
#!/usr/local/bin/python
# latin-1    # 不符合
import os
import sys
...
```
- 错误示例：编码申明不在第1、第2行
```python
#!/usr/local/bin/python
#
# -*- coding: latin-1 -*-       # 不符合
import os
import sys
...
```
- 错误示例：不支持的编码方式
```python
#!/usr/local/bin/python
# -*- coding: utf-42 -*-         # 不符合
import os
import sys
...
```
##### 场景2：文件实际编码和申明编码不符
- 错误示例：

```
**【修复建议】**

文件编码统一使用utf-8格式编码，或者文件开头使用# coding: utf-8进行编码声明。

文件开头注释中的编码申明，不代表文件的实际编码格式，工具检查的是文件的实际编码格式。

如果使用了utf-8编码申明仍然有告警，则说明文件实际编码和编码申明不一致。

需要使用notepad++或VSCode等软件查看文件实际编码，然后将文件编码转换为utf-8编码。

注意文件编码是否带windows系统的bom头，如果带bom头标志，则会触发告警，需要用软件将文件编码utf-8-bom转换为utf-8编码。
