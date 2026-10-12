# DC.G.FUN.01 禁止使用不同语言版本间不兼容的函数

- **规则ID**：775167b8-8e4e-4a58-b20f-1fda9ca9bde5
- **更新时间**：2026-04-07 04:45:01

---

**【问题级别】**

严重

**【描述】**

行号：xxx，列号：xxx：禁止使用存在语言版本不兼容函数xxx

**【正确示例】**

```
```
不兼容函数如下：
math.fmod
table.move
table.pack
table.unpack
string.pack
string.unpack
string.packsize
```

```
**【错误示例】**

```
```
math.fmod(x, y)
table.move(a, f, e, t)
table.pack(...)
table.unpack(list, i, j)
string.pack(fmt, v1, v2, ...)
string.unpack(fmt, s, pos)
string.packsize(fmt)
```

```
**【修复建议】**

数通当前使用的是Lua5.3和luajit两个版本，当产品存在Lua5.3和luajit版本混用的场景时，使用以下Lua5.3新增但在luajit上不存在的函数会存在兼容性问题，因此禁止在混用场景下使用。

math.fmod

table.move

table.pack

table.unpack

string.pack

string.unpack

string.packsize
