# G.PRJ.03 Shell脚本第一行必须通过Shebang指定Shell解释器(试点)

- **规则ID**：a56bcd05-cd8a-4058-a303-52c6c1de05dc
- **更新时间**：2025-06-05 04:30:01

---

**【问题级别】**

严重

**【描述】**

Shell脚本第一行必须通过Shebang指定Shell解释器。建议使用bash作为Shell解释器。

**【正确示例】**

```
#!/bin/bash
  echo 'test'

```
**【错误示例】**

```
echo 'test'
  # 没有使用shebang指定解释器

```
**【修复建议】**

- Shell脚本第一行必须通过Shebang指定Shell解释器。

- 建议使用bash作为Shell解释器

- Shell解释器要使用绝对路径

- Shebang不能指向一个目录

- shebang中需要移除"#"号前的空格

- shebang中需要移除"#"和"!"之间的空格
