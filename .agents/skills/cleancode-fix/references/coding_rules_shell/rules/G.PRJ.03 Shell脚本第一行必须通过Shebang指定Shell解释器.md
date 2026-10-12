# G.PRJ.03 Shell脚本第一行必须通过Shebang指定Shell解释器

- **规则ID**：dcd5bae5-0b8f-4f7c-92e9-488b949186d3
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

Shell脚本第一行必须通过Shebang指定Shell解释器；建议使用bash作为Shell解释器。

**【正确示例】**

```
```shell
#!/bin/bash
echo 'test'
```

```
**【错误示例】**

```
```shell
echo 'test'
# 没有使用shebang指定解释器
```

```
**【修复建议】**

1. Shell脚本第一行必须通过Shebang指定Shell解释器。

2. 建议使用bash作为Shell解释器。

3. Shell解释器要使用绝对路径。

4. Shebang不能指向一个目录。

5. shebang中需要移除"#"号前的空格。

6. shebang中需要移除"#"和"!"之间的空格。
