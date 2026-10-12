# DC.G.MOD.02 检查模块名是否和内置模块名重名

- **规则ID**：f16539d0-b1f3-4209-b64f-1b2947045066
- **更新时间**：2026-04-07 04:45:02

---

**【问题级别】**

严重

**【描述】**

模块名不建议使用内置模块名“xxx”

**【正确示例】**

```
```
常见的语言内置模块名如下：
coroutine
debug
file
io
math
os
package
string
table
utf8
```

```
**【错误示例】**

```
```
module("debug", package.seeall) -- 和内置模块debug重名
```

```
**【修复建议】**

数据通信产品开发场景下，通常不需要覆盖原有语言的内置实现。据此推断，如果出现自定义模块名和语言内置模块名重名，这很可能是编码疏忽而非有意设计，进而导致非预期功能错误，因此须确保模块名与语言内置模块名不重名。

常见的语言内置模块名如下：

coroutine

debug

file

io

math

os

package

string

table

utf8
