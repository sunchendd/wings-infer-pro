# G.NAM.08 布尔型变量建议以表达是非意义的动词开头

- **规则ID**：c2cf79ce-1f82-48e6-921a-f0c372d88638
- **更新时间**：2025-06-05 04:00:06

---

**【问题级别】**

提示

**【描述】**

布尔型变量建议以表达是非意义的动词开头



工具检查场景:

- 检查布尔变量名是否以是非意义的动词（is, has, can, should）开头

**【正确示例】**

```
boolean isError; 
boolean hasLicense; 
boolean canEvaluate; 
boolean shouldAbort = false;

```
**【错误示例】**

```
boolean error;
boolean found;

```
**【修复建议】**

修改变量名，增加是非意义的动词
