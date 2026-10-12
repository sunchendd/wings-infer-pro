# G.TYP.01 确保除法运算和模运算中的除数不为0(试点)

- **规则ID**：3f3e483e-0644-4972-8457-34d3fce3ffd9
- **更新时间**：2025-06-05 04:30:01

---

**【问题级别】**

严重

**【描述】**

避免除零错误，需要判断除数是否为0。

**【正确示例】**

```
#!/bin/bash
block_count=8
cpu_use=0
if [[ ${cpu_use} -ne 0 ]]; then
    align_num=$((block_count/cpu_use))
    echo "align_num:${align_num}"
fi

```
**【错误示例】**

```
#!/bin/bash
block_count=8
cpu_use=0
align_num=$((block_count/cpu_use))
echo "align_num:${align_num}"

```
**【修复建议】**

1. 在除法或模运算前判断除数是否为0。

2. 若除法或模运算在函数体内且函数体内未判断除数是否为0，也可以在函数调用处做判断。
