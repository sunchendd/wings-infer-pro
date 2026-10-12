# G.FIO.05 构造文件路径时应屏蔽操作系统的差异，建议使用库函数辅助构造

- **规则ID**：97177885-ce46-441c-9ecc-109a42f38bd8
- **更新时间**：2026-04-07 04:15:03

---

**【问题级别】**

一般

**【描述】**

不同的操作系统使用不同的字符作为路径分隔符。例如，Windows系统使用`\`，而UNIX系统使用`/`。 

当应用程序必须在不同的平台上运行时，使用硬编码的路径分隔符可能会导致应用程序逻辑执行不正确。

**【正确示例】**

```
##### 场景1：路径操作
- 修复示例：使用`os`库辅助构造，路径格式和操作系统无关 
```python 
import os 
 
 
file_name = 'tmp.txt' 
 
file_path2 = os.getcwd() + os.sep + file_name  # 符合，/mnt/d/code/test/tmp.txt 
file_path3 = os.path.join(os.getcwd(), file_name)  # 符合，/mnt/d/code/test/tmp.txt 
```

```
**【错误示例】**

```
##### 场景1：路径操作
- 错误示例：使用带有操作系统特有的路径格式 
```python 
import os 
 
 
file_name = 'tmp.txt' 
file_path1 = os.getcwd() + '\\' + file_name  # 不符合，该路径在Linux操作系统无法使用: /mnt/d/code/test\tmp.txt 
```

```
**【修复建议】**

使用`os`，`pathlib`库来操作路径。
