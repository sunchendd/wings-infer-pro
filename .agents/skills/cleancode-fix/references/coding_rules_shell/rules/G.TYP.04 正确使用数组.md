# G.TYP.04 正确使用数组

- **规则ID**：9015efb2-b03c-41cd-b39b-1c600a10e17b
- **更新时间**：2026-04-07 04:30:01

---

**【问题级别】**

严重

**【描述】**

1. Shell中数组定义的语法:array_name=(value1 value2 ... valuen)。

2. 关联数组使用declare命令来声明，语法格式：declare -A array_name。  

3. 读取数组元素值的一般格式为：${array_name[index]}。

**【正确示例】**

```
```shell
#!/bin/bash
# 使用空格分隔数组的元素
array=("what" "is" "your" "name")
# ${array[0]}的内容是'what'
echo "${array[0]}"

declare -A site=(["huawei"]="www.huawei.com" ["hiascend"]="www.hiascend.com")
# ${site["huawei"]}的内容是www.huawei.com
echo "${site["huawei"]}"
```

```
**【错误示例】**

```
```shell
#!/bin/bash
# 使用逗号+空格分隔数组的元素
array=("what", "is", "your", "name")
# ${array[0]}的内容是'what,'
echo "${array[0]}"

# 使用逗号分隔数组的元素
array=("what","is","your","name")
# ${array[0]}的内容是'what,is,your,name'
echo "${array[0]}"

# 使用逗号+空格风格关联数组中的元素
declare -A site=(["huawei"]="www.huawei.com", ["hiascend"]="www.hiascend.com")
# ${site["huawei"]}的内容是www.huawei.com,
echo "${site["huawei"]}"
```

```
**【修复建议】**

数组定义：使用空格分隔数组的元素 array=("what" "is" "your" "name") ；数组下标不能为空字符。

数组访问：数组先定义在访问；访问数组时请使用大括号 ${sentence[n]}。
