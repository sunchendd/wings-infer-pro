# G.CTL.03 在case语句中，变量需要使用双引号包围

- **规则ID**：a3d944d2-03af-492a-8498-654cfa2a3e9c
- **更新时间**：2026-04-07 04:30:00

---

**【问题级别】**

严重

**【描述】**

如果在case语句中，变量不使用双引号包围，在有些情况下会被解释成列表，可能出现不能匹配的情况。

**【正确示例】**

```
```shell
#!/bin/bash
a="value[0]"
b="value[0]"
case $a in
    -)
        echo "case -"
        ;;
    "$b")
        echo "case b" 
        ;;
esac
```

```
**【错误示例】**

```
```shell
#!/bin/bash
a="value[0]"
b="value[0]"
case $a in
    -)
        echo "case -"
        ;;
    $b)
        echo "case b" 
        ;;
esac
```

```
**【修复建议】**

在case语句中，如果分支匹配语句是变量取值，需要添加双引号。
