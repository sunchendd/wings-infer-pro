# G.MET.05 对于返回数组或者容器的方法，应返回长度为0的数组或者容器，代替返回null

- **规则ID**：f67396b2-2788-47ab-ae12-2774f04cceb7
- **更新时间**：2026-04-07 04:00:02

---

**【问题级别】**

提示

**【描述】**

在方法返回值中，用长度为`0`的数组或者容器，来代替返回`null`，则上层调用代码在使用此返回的数组或者容器前，无需再判断是否为空，业务逻辑一气呵成，代码更简洁。



同时，也避免了程序员因为忘记了对返回值进行空指针检查，而导致的NullPointerException。

**【正确示例】**

```
##### 场景1：
- 修复示例1：返回空的集合

  ```java
    public static List<String> decorate(String[] personDescs) {
        if (personDescs == null || personDescs.length == 0) {
            return Collections.emptyList(); // 返回空的集合，上层调用不需要判空，代码书写更流畅
        }
        List<String> personNames = new ArrayList<>(personDescs.length);
        for (String personDesc : personDescs) {
            String personName = getPersonName(personDesc);
            personNames.add(personName);
        }
        return personNames;
    }
  ```
- 修复示例2：通过`@Nullable`标明返回值可以为`null`

  ```java
    @Nullable
    public static List<String> decorate(String[] personDescs) {
        if (personDescs == null || personDescs.length == 0) {
            return null; // 返回null，上层代码需要对该返回值判null，否则会出现NPE
        }
        List<String> personNames = new ArrayList<>(personDescs.length);
        for (String personDesc : personDescs) {
            String personName = getPersonName(personDesc);
            personNames.add(personName);
        }
        return personNames;
    }
  ```


```
**【错误示例】**

```
##### 场景1：
- 错误示例：

  ```java
    public static List<String> decorate(String[] personDescs) {
        if (personDescs == null || personDescs.length == 0) {
            return null; // 返回null，上层代码需要对该返回值判null，否则会出现NPE
        }
        List<String> personNames = new ArrayList<>(personDescs.length);
        for (String personDesc : personDescs) {
            String personName = getPersonName(personDesc);
            personNames.add(personName);
        }
        return personNames;
    }
  ```


```
**【修复建议】**

用长度为`0`的数组或者容器，来代替返回`null`,或者通过@Nullable标明返回值可以为`null`
