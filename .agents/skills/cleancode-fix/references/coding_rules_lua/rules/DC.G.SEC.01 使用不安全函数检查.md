# DC.G.SEC.01 使用不安全函数检查

- **规则ID**：7d16624e-5fcb-48f6-83dc-43e5d2f769ac
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：禁止使用不安全函数xxx

**【正确示例】**

```
```
不安全函数如下：
dofile
loadstring
loadfile
package.searchpath
os.execute
io.popen
setfenv.getenv
loadlib
gcinfo
```

```
**【错误示例】**

```
```
dofile(filename)
local file = io.popen(command, mode)
```

```
**【修复建议】**

以下函数在《华为Lua语言编程规范2.0》的“P.06 对不可信数据校验后使用”中描述了相应的安全风险，且在数通产品绝大部分开发场景下可以避免使用，因此禁止使用这些函数。

dofile

load

loadstring (lua 5.2 已经删除)

loadfile

package.searchpath

package.loadlib

os.execute

io.popen
