# G.SER.08 禁止直接将外部数据进行反序列化

- **规则ID**：5845c46c-824b-445e-a0f5-b83d271e6476
- **更新时间**：2026-04-07 04:00:04

---

**【问题级别】**

严重

**【描述】**

许多平台支持动态执行代码，例如JavaScript的eval函数可以执行JavaScript语句，Java的反射机制可以根据字符串形式的类名和方法名动态生成类实例并执行方法，反序列化操作可以动态构造Java对象并执行其`readObject()`方法。如果用户输入被合入可动态执行的代码中，那么攻击者就可以提交精心构造的数据、混入自己的代码，让服务器执行。

**【正确示例】**

```
##### 场景：使用@Value注入外部数据
-修复示例：
 ```java
 @Valid
 @Value(${com.huawei.config.path})
 private String path;
 
 public void doSomething() {
     String canonicalPath = path;
     if (!validatePath(canonicalPath)) {
         throw new IllegalArgumentException("Path Traversal vulnerability!");
     }
     File file = new File(HOME_PATH, canonicalPath);
     try {
         ... // 对文件进行读写等操作
     } catch (IOException ex) {
         throw new IllegalArgumentException("An exception occurred ...", ex);
     }
 }
 private boolean validatePath(String path) { // 自定义校验函数
     return path.startsWith(HOME_PATH); // 举例
 }
 ```

### 场景1：使用`ScriptEngineManager`执行脚本代码
##### 场景1：使用`ScriptEngineManager`执行脚本代码
- 修复示例1：
```java
private static void doSomething() {        
    String jsCode = request.getParameter("jscode");
    jsCode =  validateJson(jsCode);
    ...
    NashornSandbox sandbox = new NashornSandboxes();
    sandbox.allow(File.class);  //使用sandbox.allow()来设置允许使用的java类
    sandbox.eval(jsCode);
    ...
}

private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
- 修复示例2：
 ```java
 @Valid
 @Value(${com.huawei.config.json})
 private String json;
 
 public void doSomething() {
     String jsonString = json;
     if (!validateJson(jsonString )) {
         throw new IllegalArgumentException("Json Traversal vulnerability!");
     }
    ...
 }
private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
 ```
##### 场景2：使用Fastjson 1.2.68以前版本
- 修复示例：禁用AutoType功能,并设置白名单校验
```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
     jsonStr =  validateJson(jsonStr );
    ...
    ParserConfig.getGlobalInstance().setAutoTypeSupport(false); // 或者是直接删除该行代码
    ParserConfig.getGlobalInstance().addAccept("com.func.test.User"); // 进一步设置白名单校验规则
    User user = (User) JSONObject.parse(jsonStr);
    ...
}
private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
##### 场景3：使用Fastjson 1.2.68及以上新版本
- 修复示例1：开启SafeMode

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
     jsonStr =  validateJson(jsonStr );
    ...
    ParserConfig.getGlobalInstance().setSafeMode(true);
    User user = (User) JSONObject.parse(jsonStr);
    ...
}

private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
- 修复示例2：解析Json字符串时，开启SafeMode模式

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
     jsonStr =  validateJson(jsonStr );
    ...
    ParserConfig.getGlobalInstance().setSafeMode(true);
    User user = JSON.parseObject(jsonStr, User.class, Feature.SafeMode);
    ...
}

private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
##### 场景4：使用Jackson
- 修复示例1：对于Jackson 2.10.0以前的版本

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
     jsonStr =  validateJson(jsonStr );
    ...
    ObjectMapper mapper = new ObjectMapper();
    mapper.disableDefaultTyping();
    UserInfo demo = (UserInfo)mapper.readValue(jsonStr, UserInfo.class);
    ...
}
private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
- 修复示例2：对于Jackson 2.10.0及新版本

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
     jsonStr =  validateJson(jsonStr );
    ...
    ObjectMapper mapper = new ObjectMapper();
    mapper.activeDefaultTyping(...);
    UserInfo demo = (UserInfo)mapper.readValue(jsonStr, UserInfo.class);
    ...
}
private String validateJson(String json) { // 自定义校验函数
    return json.replace("\r", "").replace("
", ""); // 举例
}
```
##### 场景5：使用XStream
- 修复示例1：启用白名单校验

```java
private static void doSomething() {        
    String xmlStr = request.getParameter("xmlData");
    if (!validateXml(xmlStr )) {
         throw new IllegalArgumentException("Path Traversal vulnerability!");
     }
    ...
    XStream xst = new XStream(new DomDriver());

    // 首先清除默认设置，然后进行自定义设置
    xst.addPermission(NoTypePermission.NONE);

    // 添加一些基础的类型，如Array、NULL、primitive
    xst.addPermission(ArrayTypePermission.ARRAYS);
    xst.addPermission(NullPermission.NULL);
    xst.addPermission(PrimitiveTypePermission.PRIMITIVES);

    // 添加自定义的类列表
    xst.addPermission(new ExplicitTypePermission(new Class[] { XStreamTest.class }));

    // 添加同一个package下的多个类型
    xst.allowTypesByWildcard(new String[] { XStreamTest.class.getPackage().getName() + ".*" });
    xst.fromXML(xmlStr);
}

 private boolean validateXml(String xml) { // 自定义校验函数
     return xml.startsWith(HOME_PATH); // 举例
 }
```
- 修复示例2：XStream-1.4.10及以上版本,设置默认安全校验

```java
private static void doSomething() {        
    String xmlStr = request.getParameter("xmlData");
    if (!validateXml(xmlStr )) {
         throw new IllegalArgumentException("Path Traversal vulnerability!");
     }
    ...
    XStream xst = new XStream(new DomDriver());
    XStream.setupDefaultSecurity(xst);
    xst.fromXML(xmlStr);
}
 private boolean validateXml(String xml) { // 自定义校验函数
     return xml.startsWith(HOME_PATH); // 举例
 }
```
##### 场景6：使用XMLDecoder
- 修复示例：将XMLDecoder改为XStream

```java
private static void doSomething() {        
    String xmlStr = request.getParameter("xmlData");
    if (!validateXml(xmlStr )) {
         throw new IllegalArgumentException("Path Traversal vulnerability!");
     }
    ...
    XStream xst = new XStream(new DomDriver());
    XStream.setupDefaultSecurity(xst);
    xst.fromXML(xmlStr);
}
 private boolean validateXml(String xml) { // 自定义校验函数
     return xml.startsWith(HOME_PATH); // 举例
 }
```
##### 场景7：使用SnakeYaml
- 修复示例1：

```java
private static void doSomething() {        
    String yamlStr = request.getParameter("yamlData");
    if (!validateYaml(yamlStr )) {
         throw new IllegalArgumentException("Path Traversal vulnerability!");
     }
    ...
    Yaml yaml = new Yaml(new SnakeYamlSecureConstructor());
    yaml.load(yamlStr);
}
 private boolean validateXml(String yaml) { // 自定义校验函数
     return yaml.startsWith(HOME_PATH); // 举例
 }

class SnakeYamlSecureConstructor extends Constructor {
    SnakeYamlSecureConstructor(DeserializeAcceptedClassList whiteList) {
        super();

        this.yamlConstructors.put(null, undefinedConstructor); // 禁止所有的未定义的类进行构造
        addWhiteList(whiteList);  // 增加白名单类的构造
    }

    private void addWhiteList(DeserializeAcceptedClassList whiteList) {
        if (whiteList == null) {
            return;
        }

        for (String whiteName: whiteList) {
            this.yamlConstructors.put(new Tag(Tag.PREFIX + whiteName), new SecureConstructObject());
        }
    }

    /**
     * ConstructYamlObject是Constructor类中的保护类，非静态，所以内部含有Constructor的指针，不能在外部直接引用
     * 所以使用继承的方式，将SnakeYamlDeserializeConstructor指针赋值到SecureConstructObject内部，并保持ConstructYamlObject
     * 的行为不变化
     */
    protected class SecureConstructObject extends ConstructYamlObject {
        SecureConstructObject() {
            super();
        }
    }
}
```
- 修复示例2：使用自定义函数校验外部数据。
 
```java
private static void doSomething() {        
    String yamlStr = request.getParameter("yamlData");
    ...
    Yaml yaml = new Yaml();
    if (!validYaml(yamlStr)) { // valid开头的自定义校验函数校验
        throw new Exception("XXX");
    }
    yaml.load(yamlStr);
}

private static Boolean validYaml(String yamlStr){
    ...// 产品自定义校验逻辑
}
```

```
**【错误示例】**

```
##### 场景1：使用`ScriptEngineManager`执行脚本代码
- 错误示例：
```java
private static void doSomething() {        
    String jsCode = request.getParameter("jscode");
    ...
    ScriptEngineManager manager = new ScriptEngineManager();
    ScriptEngine engine = manager.getEngineByName("javascript");
    engine.eval(jsCode);
    ...
}
```
##### 场景2：使用Fastjson 1.2.68以前版本
- 错误示例：开启AutoType功能

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
    ...
    ParserConfig.getGlobalInstance().setAutoTypeSupport(true);
    User user = (User) JSONObject.parse(jsonStr);
    ...
}
```
##### 场景3：使用Fastjson 1.2.68及以上新版本
- 错误示例：禁用SafeMode

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
    ...
    ParserConfig.getGlobalInstance().setSafeMode(false);
    User user = (User) JSONObject.parse(jsonStr);
    ...
}
```
##### 场景4：使用Jackson
- 错误示例：

```java
private static void doSomething() {        
    String jsonStr = request.getParameter("jsonData");
    ...
    ObjectMapper mapper = new ObjectMapper();
    mapper.enableDefaultTyping();
    UserInfo demo = (UserInfo)mapper.readValue(jsonStr, UserInfo.class);
    ...
}
```
##### 场景5：使用XStream
- 错误示例：

```java
private static void doSomething() {        
    String xmlStr = request.getParameter("xmlData");
    ...
    XStream xst = new XStream(new DomDriver());
    xst.fromXML(xmlStr);
    ...
}
```
##### 场景6：使用XMLDecoder
- 错误示例：

```java
private static void doSomething() {
    ...
    InputStream is = request.getInputStream();
    ...
    XMLDecoder decoder = new XMLDecoder(is);
    decoder.readObject();
}
```
##### 场景7：使用SnakeYaml
- 错误示例：

```java
private static void doSomething() {        
    String yamlStr = request.getParameter("yamlData");
    ...
    Yaml yaml = new Yaml();
    yaml.load(yamlStr);
}
```

```
**【修复建议】**

1、对于使用`ScriptEngineManager`执行脚本代码的场景：

- 推荐使用`nashornsandbox`沙箱机制执行执行脚本代码。



2、对于不安全反序列化场景：



2.1、对于Json字符串的反序列化操作：



1） Fastjson组件：

- 对于使用Fastjson 1.2.68以前版本，通过`ParserConfig.getGlobalInstance().setAutoTypeSupport(true)`方式开启type功能时，存在安全风险，需要删除该行代码(默认值为false)或`setAutoTypeSupport(false)`；

- 对于使用Fastjson 1.2.68及以上版本，Fastjson在1.2.68及以后版本引入SafeMode，通过开启SafeMode模式，规避不安全反序列化风险，具体设置方式：全局配置`ParserConfig.getGlobalInstance().setSafeMode(true)`，针对某个解析配置`JSON.ParseObject(str, xx.class, Feature.SafeMode)`.



2） Jackson组件：

通过`ObjectMapper.enableDefaultTyping()`方法类似fastjson中的autotype功能，容易导致不安全反序列化风险。该方法从2.10.0开始被标注为`@Deprecated`，推荐使用`activateDefaultTyping()`方法替代。针对Jackson不安全反序列化问题的防护：

- 对于2.10.0以前的版本，将`ObjectMapper.enableDefaultTyping()`改为`ObjectMapper.disableDefaultTyping()`；

- 对于2.10.0及新版本，将`ObjectMapper.enableDefaultTyping()`改为使用`activateDefaultTyping()`方法。



2.2、对于XML字符串的反序列化操作：



1） 使用XStream：

- 使用白名单校验方式对反序列化操作的目标class进行校验；

- 对于使用1.4.10及以上版本，设置默认安全校验。



2） 使用XMLDecoder

- java原生的XMLDecoder类常被用来序列化反序列化XML格式数据，但是这个类也存在严重安全问题，这里解析任意xml文件可以导致反序列化命令执行，oracle官方未提供任何针对此问题的安全措施，所以在反序列化不可信xml数据时，应该使用XStream替代XMLDecoder。



2.3、对于yaml字符串的反序列化操作：

- 使用白名单校验方式对反序列化操作的目标class进行校验。
