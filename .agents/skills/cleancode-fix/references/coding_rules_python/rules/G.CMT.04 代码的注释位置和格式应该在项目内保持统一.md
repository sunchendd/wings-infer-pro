# G.CMT.04 代码的注释位置和格式应该在项目内保持统一

- **规则ID**：515207e8-5325-41ec-af33-e80ef6c4934a
- **更新时间**：2026-04-07 04:15:02

---

**【问题级别】**

一般

**【描述】**

代码的注释位置和格式应该在项目内保持统一风格，否则会导致代码很难维护，可读性差。

**【正确示例】**

```
##### 场景1：注释在代码段的上方
- 修复示例：注释放在语句块上方，并和被注释代码段保持同样的缩进。#后面空一格写注释内容
```python
 # Create command line to call pylint
 epylint_part = [executable, "-c", "from pylint import epylint;epylint.Run()"]
```
##### 场景2：注释在行尾
- 修复示例：注释放在行尾，与代码尾部间隔至少两个空格
```python
repssn_ind = ssn_data[index].repssn_index  # Get replicate sub system index and net indicator
```


```
**【错误示例】**

```
##### 场景1：注释在代码段的上方
- 错误示例：注释虽然放在代码段的上方，但没有和被注释代码段保持同样的缩进。
```python
      # Get replicate sub system index and net indicator   
repssn_ind = ssn_data[index].repssn_index
repssn_ni = ssn_data[index].ni
```
##### 场景2：注释在行尾
- 错误示例：注释放在了被注释代码段的下方。
```python
 epylint_part = [executable, "-c", "from pylint import epylint;epylint.Run()"]
 # Create command line to call pylint
```


```
**【修复建议】**

1. 注释应该与其描述的代码保持同样的缩进，放在被注释代码块的上方相邻位置，使用#开头，#后面一个空格然后写注释文本。

2. 代码行的行尾添加注释，为了提高可读性，行尾注释应该至少离开代码2个空格，#后面一个空格然后写注释文本。
