/// Dynamsoft JavaScript Library
/// @product Dynamsoft SDK
/// @website https://www.dynamsoft.com
/// 
/// @preserve Copyright 2019, Dynamsoft Corporation
/// @author Dynamsoft R&D Team
/// 
/// @version 5.2.1
/// 
var Dynamsoft = Dynamsoft || {};
(function (global, dynam, nil) {

    "use strict";
	
	var _preDefine_ver = 20200521;

	if (dynam._preDefine_ver) {
		if (dynam._preDefine_ver >= _preDefine_ver) {
			return;
		}
	}
	dynam._preDefine_ver = _preDefine_ver;
	
    var mix = function (dest, source) {
            for (var i in source) {
				if (source.hasOwnProperty(i)) {
					dest[i] = source[i];
				}
            }

            return dest;
        },
		clone = function (obj) {
			// Handle the 3 simple types, and null or undefined
			if (null == obj || "object" != typeof obj) return obj;

			var copy, i, len;
			if (obj instanceof Date) { // Handle Date
				copy = new Date();
				copy.setTime(obj.getTime());
				return copy;
			} else if (obj instanceof Array) {	// Handle Array
				copy = [];
				len = obj.length;
				for (i=0; i < len; i++) {
					copy[i] = clone(obj[i]);
				}
				return copy;
			} else if (obj instanceof Object) { // Handle Object
				copy = {};
				for (i in obj) {
					if (obj.hasOwnProperty(i)) copy[i] = clone(obj[i]);
				}
				return copy;
			} else {
				return 0;
			}
		};
		
	if(!dynam.Lib)
		dynam.Lib={};
	


    mix(dynam.Lib, {
        win: global,
        doc: global.document,
        debug: !1,		// false
        nil: nil,

        mix: mix,
		clone: clone,
		keys: Object.keys,
        guid: function (pre) {
			var s = [], hexDigits = "0123456789abcdef", i, tmp;
			
			for (i = 0; i < 8; i++) {
				s.push(hexDigits.substr(Math.floor(Math.random() * 0x10), 1));
			}
			s.push('-');
			for (i = 0; i < 4; i++) {
				s.push(hexDigits.substr(Math.floor(Math.random() * 0x10), 1));
			}
			s.push('-4');
			for (i = 0; i < 3; i++) {
				s.push(hexDigits.substr(Math.floor(Math.random() * 0x10), 1));
			}
			s.push('-');
			tmp = hexDigits.substr(Math.floor(Math.random() * 0x10), 1);
			tmp = hexDigits.substr((tmp & 0x3) | 0x8, 1);
			s.push(tmp);
			
			for (i = 0; i < 3; i++) {
				s.push(hexDigits.substr(Math.floor(Math.random() * 0x10), 1));
			}
			s.push('-');
			for (i = 0; i < 8; i++) {
				s.push(hexDigits.substr(Math.floor(Math.random() * 0x10), 1));
			}
			
			s.unshift(pre);
			return s.join('');
        },

        now: Date.now || function () {
            return +new Date();
        },
        noop: function () { }
    });

})(typeof window !== "undefined" ? window : this, Dynamsoft);


(function(lib){
	
    "use strict";

    var hasEnumBug = !({ toString: 1 }.propertyIsEnumerable('toString')),
        enumProperties = [
            'constructor',
            'hasOwnProperty',
            'isPrototypeOf',
            'propertyIsEnumerable',
            'toString',
            'toLocaleString',
            'valueOf'
        ];
		
    function hasOwnProperty(o, p) {
        return ({}).hasOwnProperty.call(o, p);
    }
	
    // get all the property names of an array object
    lib.keys = Object.keys || function(o) {
        var result = [], p, i;

        for (p in o) {
            // lib.keys(new XX())
            if (hasOwnProperty(o, p)) {
                result.push(p);
            }
        }

        if (hasEnumBug) {
            for (i = enumProperties.length - 1; i >= 0; i--) {
                p = enumProperties[i];
                if (hasOwnProperty(o, p)) {
                    result.push(p);
                }
            }
        }

        return result;
    };
	
})(Dynamsoft.Lib);(function (lib, nil) {
    "use strict";

	var _isXXX_ver = 20200716;
	if (lib._isXXX_ver) {
		if (lib._isXXX_ver >= _isXXX_ver) {
			return;
		}
	}
	lib._isXXX_ver = _isXXX_ver;
	
    var mix = lib.mix, each, types,
        FALSE = !1, TRUE = !0,
        _console = FALSE,
		hasOwnProperty = {}.hasOwnProperty,
        class2TypeMap = {},
		isHTMLElementObject = ( typeof HTMLElement === 'object' );

    function isNil(o) {
        return o === nil;
    }

    function isDef(o) {
        return o !== nil;
    }

    // type judgement: isDef / isUndef / isUndefined / isNull / isString / isFunction / isObject / 
    // isArray / isBoolean / isNumber / isPlainObject
    mix(lib, {
        'isDef': isDef,
        'isUndef': isNil,
        'isUndefined': isNil,

        'isNull': function (o) {
            return (o === null);
        },

        'isNaN': function (o) {
            return isNaN(o);
        },

        'type': function (o) {
            if (o === null || o === nil)
                return String(o);
            return class2TypeMap[{}.toString.call(o)] || 'object';
        },

        // checks to see if an object is a plain object (created using '{}'
        // or 'new Object()' but not 'new FunctionClass()')
        isPlainObject: function (obj) {
            // Must be an Object.
            // Because of IE, we also have to check the presence of the constructor property.
            // Make sure that Dom nodes and window objects don't pass through, as well
            if (!obj || lib.type(obj) !== 'object' || obj.nodeType ||
                // jshint eqeqeq:false
                // must == for ie8
                obj.window == obj) {
                return FALSE;
            }

            var key, objConstructor;

            try {
                // Not own constructor property must be Object
                if ((objConstructor = obj.constructor) &&
                    !hasOwnProperty(obj, 'constructor') &&
                    !hasOwnProperty(objConstructor.prototype, 'isPrototypeOf')) {
                    return FALSE;
                }
            } catch (e) {
                // IE8,9 Will throw exceptions on certain host objects
                return FALSE;
            }

            // Own properties are enumerated firstly, so to speed up,
            // if last one is own, then all properties are own.
            // jshint noempty:false
            for (key in obj) {
            }

            return (isNil(key) || hasOwnProperty(obj, key));
        },
		
		isDOM: function(obj) {
			return isHTMLElementObject ?
				(obj instanceof HTMLElement) :
				obj && typeof obj === 'object' && (obj.nodeType === 1 || obj.nodeType === 9) && typeof obj.nodeName === 'string';
		},
		
		isDOMInBody: function(obj) {
			var el = obj;
			
			if(lib.isDOM(obj))
				while(!el && el != document.body)
					el = el.parentNode;
			else 
				el = 0;
			return !!el;
		}
		
    });
	

    function mixIsFunctions(name, lc) {
        // populate the class2type map
        class2TypeMap['[object ' + name + ']'] = (lc = name.toLowerCase());

        // add isBoolean/isNumber/...
        lib['is' + name] = function (o) {
            return lib.type(o) === lc;
        };
    }

    // add isFunction
    mixIsFunctions('Function');

    // each
    lib.each = each = function (object, fn, context) {
        if (object) {
            var key,
                val,
                keys,
                i = 0,
                length = object.length,
                // do not use typeof obj == 'function': bug in phantomjs
                isObj = isNil(length) || lib.isFunction(object);

            context = context || null;

            if (isObj) {
                keys = lib.keys(object);
                for (; i < keys.length; i++) {
                    key = keys[i];
                    // can not use hasOwnProperty
                    if (fn.call(context, object[key], key, object) === FALSE) {
                        break;
                    }
                }
            } else {
                for (val = object[0];
                    i < length; val = object[++i]) {
                    if (fn.call(context, val, i, object) === FALSE) {
                        break;
                    }
                }
            }
        }

        return object;
    };

    types = ['String', 'Object', 'Boolean', 'Number'];
    if (Array.isArray) {
        lib.isArray = Array.isArray;
    } else {
        types.push('Array');
    }

    each(types, mixIsFunctions);

})(Dynamsoft.Lib);
(function (lib) {
    "use strict";

    var mix = lib.mix,
        win = lib.win,
		_console;
		
	var _log_ver = 20200521;
		
	if (lib._log_ver) {
		if (lib.isNumber(lib._log_ver) && lib._log_ver >= _log_ver) {
			return;
		}
	}
	lib._log_ver = _log_ver;
	
    if (lib.isDef(win.console)) {
        _console = win.console;
        if (!lib.isFunction(_console.log) || !lib.isFunction(_console.error)) {
            _console = false;
        }
    }

    // log
    mix(lib, {

        'log': function (txt) {
            if (lib.debug && _console) {
                _console.log(txt);
            }
        },
        'error': function (txt) {
            if (lib.debug && _console) {
                _console.error(txt);
            }
        },

        'getLogger': function () {
            var _ = lib.log;
            return { warn: _, log: _, info: _, debug: _ };
        }
    });
})(Dynamsoft.Lib);(function (lib) {

    "use strict";

    var _random_ver = 20200521;
    if (lib._random_ver) {
        if (lib._random_ver >= _random_ver) {
            return;
        }
    }
    lib._random_ver = _random_ver;
	
    lib.getRandom = function () {
        var a = lib.now() % 1e4,
            b = [],
            tmp;

        for (var i = 0; i < 5; i++) {
            tmp = Math.floor(Math.random() * 10);
            if (i == 0 && tmp == 0) {
                i = -1;
                continue;
            }
            b.push(tmp);
        }

        if (a < 10) {
            b.push('000');
        } else if (a < 100) {
            b.push('00');
        } else if (a < 1e3) {
            b.push('0');
        }
        b.push(a);

        return b.join('');
    };

})(Dynamsoft.Lib);(function (lib) {

    "use strict";
	var _strUtil_ver = 20200521;
		
	if (lib._strUtil_ver) {
		if (lib.isNumber(lib._strUtil_ver) && lib._strUtil_ver >= _strUtil_ver) {
			return;
		}
	}
	lib._strUtil_ver = _strUtil_ver;
	
    // string startsWith/endsWith/replaceAll
    lib.mix(lib, {
        startsWith: function (str, prefix) {
            return str.lastIndexOf(prefix, 0) === 0;
        },

        endsWith: function (str, suffix) {
            var ind = str.length - suffix.length;
            return ind >= 0 && str.indexOf(suffix, ind) === ind;
        },

        replaceAll: function (str, sFind, sReplace) {
            return str.replace(new RegExp(sFind, 'gi'), sReplace);
        },

        upperCaseFirst: function (str) {
            return str.charAt(0).toUpperCase() + str.substr(1);
        },

        makeArray: function (o) {
            if (o == null) {
                return [];
            }
            if (lib.isArray(o)) {
                return o;
            }
            var lengthType = typeof o.length,
                oType = typeof o;
            // The strings and functions also have 'length'
            if (lengthType !== 'number' ||
                // form.elements in ie78 has nodeName 'form'
                // then caution select
                // o.nodeName
                // window
                o.alert ||
                oType === 'string' ||
                // https://github.com/ariya/phantomjs/issues/11478
                (oType === 'function' && !('item' in o && lengthType === 'number'))) {
                return [o];
            }
            var ret = [];
            for (var i = 0, l = o.length; i < l; i++) {
                ret[i] = o[i];
            }
            return ret;
        }
    });

})(Dynamsoft.Lib);(function (lib) {
    "use strict";

	var _extend_ver = 20200521;
	if (lib._extend_ver) {
		if (lib.isNumber(lib._extend_ver) && lib._extend_ver >= _extend_ver) {
			return;
		}
	}
	lib._extend_ver = _extend_ver;
	
	lib.extend = function (ParentClass, childAddConstructor) {
		/// <summary>
		/// Parents constructor shouldn't has deference performances when given params more than it need.
		/// Child add constructor must has params that parent constructor need.
		/// Child add constructor could be add more params at back of parent's.<br />
		/// @return a child constructor or called a child class.
		/// </summary>
		/// <param name="ParentClass" type="function">parent constructor</param>
		/// <param name="childAddConstructor" type="function" optional="true">
		/// child add constructor,the extend has inited parent's,so only care the child.<br />
		/// @template: function( parent's params ...  [, child's params ... ]){ child operation ... }
		/// </param>
		/// <returns type="function"></returns>
		var ChildClass = function () {
			ParentClass.apply(this, arguments);
			if (childAddConstructor) {
				childAddConstructor.apply(this, arguments);
			}
		};
		
		lib.each(ParentClass.prototype, function(item, key){
			ChildClass.prototype[key] = item;
		});
		
		ChildClass.prototype.constructor = ChildClass;
		return ChildClass;
	};
})(Dynamsoft.Lib);(function (lib) {

    "use strict";
			
	var _attribute_ver = 20200521;
	if (lib._attribute_ver) {
		if (lib.isNumber(lib._attribute_ver) && lib._attribute_ver >= _attribute_ver) {
			return;
		}
	}
	lib._attribute_ver = _attribute_ver;
	
	function Attributes(config) {
		var self = this,
			c = self.constructor;
			
		self.__attrs = {};
		self.__attrVals = {};

		self.userConfig = config;
		while (c) {
			self.addAttrs(c.ATTRS);
			c = c.superclass ? c.superclass.constructor : null;
		}
		lib.mix(self.__attrs, config);
	}

	lib.mix(Attributes.prototype, {
		get: function (name) {
			var self = this;
			if (name in self.__attrs)
				return self.__attrs[name];
			return '';
		},
		set: function (name, v) {
			var self = this;
			if (name in self.__attrs)
				self.__attrs[name] = v;
		},
		addAttrs: function (attrsConfig) {
			lib.mix(this.__attrs, attrsConfig);
		}
	});

	Attributes.extend = function (px) {
		var SuperClass = this, childAddConstructor, ret;
		px = px || {};
		if (px.constructor)
			childAddConstructor = px.constructor;
		ret = lib.extend(SuperClass, childAddConstructor);
		lib.mix(ret, px);
		return ret;
	};

	lib.Attributes = Attributes;

})(Dynamsoft.Lib);/// File Description:
/// 	Provide functions to convert json object to string and vice versa.
/// 	1. lib.parse() - Parse a string as JSON and return the value.
/// 	2. lib.stringify() - Return a JSON string corresponding to the specified value.
///

(function (lib) {
		
    "use strict";
	var _json_ver = 20200521;
	if (lib._json_ver) {
		if (lib._json_ver >= _json_ver) {
			return;
		}
	}
	lib._json_ver = _json_ver;
	
	var _json = lib.win.JSON;
	if (_json && _json.parse && _json.stringify) {
		lib.parse = _json.parse;
		lib.stringify = _json.stringify;		
		return;
	}
	
    // json/quote
    var Quote = (function () {
        var CONTROL_MAP = {
            '\b': '\\b',
            '\f': '\\f',
            '\n': '\\n',
            '\r': '\\r',
            '\t': '\\t',
            '"': '\\"'
        },
            REVERSE_CONTROL_MAP = {},
            QUOTE_REG = /["\b\f\n\r\t\x00-\x1f]/g,
            UN_QUOTE_REG = /\\\\|\\\/|\\b|\\f|\\n|\\r|\\t|\\"|\\u[0-9a-zA-Z]{4}/g;

        lib.each(CONTROL_MAP, function (original, encoded) {
            REVERSE_CONTROL_MAP[original] = encoded;
        });

        REVERSE_CONTROL_MAP['\\/'] = '/';
        REVERSE_CONTROL_MAP['\\\\'] = '\\';

        return {
            quote: function (value) {
                return '"' + value.replace(QUOTE_REG, function (m) {
                    var v;
                    if (!(v = CONTROL_MAP[m])) {
                        v = '\\u' + ('0000' + m.charCodeAt(0).toString(16)).slice(0 - 4);
                    }
                    return v;
                }) + '"';
            },
            unQuote: function (value) {
                return value.slice(1, value.length - 1).replace(UN_QUOTE_REG, function (m) {
                    var v;
                    if (!(v = REVERSE_CONTROL_MAP[m])) {
                        v = String.fromCharCode(parseInt(m.slice(2), 16));
                    }
                    return v;
                });
            }
        };
    })(), str;

    // json/stringify
    function padding2(n) {
        return n < 10 ? '0' + n : n;
    }

    function jo(value, replacerFunction, propertyList, gap, stack, indent) {

        var stepBack = indent;
        indent += gap;
        var k, kl, i = 0, p;
        if (propertyList !== undefined) {
            k = propertyList;
        } else {
            k = lib.keys(value);
        }
        var partial = [];
        for (kl = k.length; i < kl; i++) {
            p = k[i];
            var strP = str(p, value, replacerFunction, propertyList, gap, stack, indent);
            if (strP !== undefined) {
                var member = Quote.quote(p);
                member += ':';
                if (gap) {
                    member += ' ';
                }
                member += strP;
                partial[partial.length] = member;
            }
        }
        var ret;
        if (!partial.length) {
            ret = '{}';
        } else {
            if (!gap) {
                ret = '{' + partial.join(',') + '}';
            } else {
                var separator = ",\n" + indent;
                var properties = partial.join(separator);
                ret = '{\n' + indent + properties + '\n' + stepBack + '}';
            }
        }
        return ret;
    }

    function ja(value, replacerFunction, propertyList, gap, stack, indent) {

        var stepBack = indent;
        indent += gap;
        var partial = [];
        var len = value.length;
        var index = 0;
        while (index < len) {
            var strP = str(String(index), value, replacerFunction, propertyList, gap, stack, indent);
            if (strP === undefined) {
                partial[partial.length] = 'null';
            } else {
                partial[partial.length] = strP;
            }
            ++index;
        }
        var ret;
        if (!partial.length) {
            ret = '[]';
        } else {
            if (!gap) {
                ret = '[' + partial.join(',') + ']';
            } else {
                var separator = '\n,' + indent;
                var properties = partial.join(separator);
                ret = '[\n' + indent + properties + '\n' + stepBack + ']';
            }
        }

        return ret;
    }

    str = function (key, holder, replacerFunction, propertyList, gap, stack, indent) {
        var value = holder[key];
        if (value && typeof value === 'object') {
            if (typeof value.toJSON === 'function') {
                value = value.toJSON(key);
            } else if (value instanceof Date) {
                value = isFinite(value.valueOf()) ?
                    value.getUTCFullYear() + '-' +
                        padding2(value.getUTCMonth() + 1) + '-' +
                        padding2(value.getUTCDate()) + 'T' +
                        padding2(value.getUTCHours()) + ':' +
                        padding2(value.getUTCMinutes()) + ':' +
                        padding2(value.getUTCSeconds()) + 'Z' : null;
            } else if (value instanceof String || value instanceof Number || value instanceof Boolean) {
                value = value.valueOf();
            }
        }
        if (replacerFunction !== undefined) {
            value = replacerFunction.call(holder, key, value);
        }

        switch (typeof value) {
            case 'number':
                return isFinite(value) ? String(value) : 'null';
            case 'string':
                return Quote.quote(value);
            case 'boolean':
                return String(value);
            case 'object':
                if (!value) {
                    return 'null';
                }
                if (lib.isArray(value)) {
                    return ja(value, replacerFunction, propertyList, gap, stack, indent);
                }
                return jo(value, replacerFunction, propertyList, gap, stack, indent);
                // ignore undefined
        }

        return undefined;
    };
	
    lib.stringify = function (value, replacer, space) {
        var gap = '';
        var propertyList, replacerFunction;
        if (replacer) {
            if (typeof replacer === 'function') {
                replacerFunction = replacer;
            } else if (lib.isArray(replacer)) {
                propertyList = replacer;
            }
        }

        if (typeof space === 'number') {
            space = Math.min(10, space);
            gap = new Array(space + 1).join(' ');
        } else if (typeof space === 'string') {
            gap = space.slice(0, 10);
        }

        return str('', {
            '': value
        }, replacerFunction, propertyList, gap, [], '');
    };

    // json/parser
    var parser = {},
        GrammarConst = {
            'SHIFT_TYPE': 1,
            'REDUCE_TYPE': 2,
            'ACCEPT_TYPE': 0,
            'TYPE_INDEX': 0,
            'PRODUCTION_INDEX': 1,
            'TO_INDEX': 2
        },
		Lexer;

    parser.yy = {
        unQuote: Quote.unQuote
    };

    Lexer = function (cfg) {

        var self = this;

        /*
         lex rules.
         @type {Object[]}
         @example
         [
         {
         regexp:'\\w+',
         state:['xx'],
         token:'c',
         // this => lex
         action:function(){}
         }
         ]
         */
        self.rules = [];

        lib.mix(self, cfg);

        /*
         Input languages
         @type {String}
         */

        self.resetInput(self.input);

    };
    Lexer.prototype = {
        'constructor': function (cfg) {

            var self = this;

            /*
             lex rules.
             @type {Object[]}
             @example
             [
             {
             regexp:'\\w+',
             state:['xx'],
             token:'c',
             // this => lex
             action:function(){}
             }
             ]
             */
            self.rules = [];

            lib.mix(self, cfg);

            /*
             Input languages
             @type {String}
             */

            self.resetInput(self.input);

        },
        'resetInput': function (input) {
            lib.mix(this, {
                input: input,
                matched: "",
                stateStack: [Lexer.STATIC.INITIAL],
                match: "",
                text: "",
                firstLine: 1,
                lineNumber: 1,
                lastLine: 1,
                firstColumn: 1,
                lastColumn: 1
            });
        },
        'getCurrentRules': function () {
            var self = this,
                currentState = self.stateStack[self.stateStack.length - 1],
                rules = [];
            currentState = self.mapState(currentState);
            lib.each(self.rules, function (r) {
                var state = r.state || r[3];
                if (!state) {
                    if (currentState == Lexer.STATIC.INITIAL) {
                        rules.push(r);
                    }
                } else if (lib.inArray(currentState, state)) {
                    rules.push(r);
                }
            });
            return rules;
        },
        'pushState': function (state) {
            this.stateStack.push(state);
        },
        'popState': function () {
            return this.stateStack.pop();
        },
        'getStateStack': function () {
            return this.stateStack;
        },
        'showDebugInfo': function () {
            var self = this,
                DEBUG_CONTEXT_LIMIT = Lexer.STATIC.DEBUG_CONTEXT_LIMIT,
                matched = self.matched,
                match = self.match,
                input = self.input;
            matched = matched.slice(0, matched.length - match.length);
            var past = (matched.length > DEBUG_CONTEXT_LIMIT ? "..." : "") + matched.slice(-DEBUG_CONTEXT_LIMIT).replace(/\n/, " "),
                next = match + input;
            next = next.slice(0, DEBUG_CONTEXT_LIMIT) + (next.length > DEBUG_CONTEXT_LIMIT ? "..." : "");
            return past + next + '\n' + new Array(past.length + 1).join("-") + "^";
        },
        'mapSymbol': function (t) {
            var self = this,
                symbolMap = self.symbolMap;
            if (!symbolMap) {
                return t;
            }
            return symbolMap[t] || (symbolMap[t] = (++self.symbolId));
        },
        'mapReverseSymbol': function (rs) {
            var self = this,
                symbolMap = self.symbolMap,
                i,
                reverseSymbolMap = self.reverseSymbolMap;
            if (!reverseSymbolMap && symbolMap) {
                reverseSymbolMap = self.reverseSymbolMap = {};
				lib.each(symbolMap, function(val, key){
					reverseSymbolMap[val] = key;
				});
            }
            if (reverseSymbolMap) {
                return reverseSymbolMap[rs];
            } else {
                return rs;
            }
        },
        'mapState': function (s) {
            var self = this,
                stateMap = self.stateMap;
            if (!stateMap) {
                return s;
            }
            return stateMap[s] || (stateMap[s] = (++self.stateId));
        },
        'lex': function () {
            var self = this,
                input = self.input,
                i,
                rule,
                m,
                ret,
                lines,
                rules = self.getCurrentRules();

            self.match = self.text = "";

            if (!input) {
                return self.mapSymbol(Lexer.STATIC.END_TAG);
            }

            for (i = 0; i < rules.length; i++) {
                rule = rules[i];
                var regexp = rule.regexp || rule[1],
                    token = rule.token || rule[0],
                    action = rule.action || rule[2] || undefined;
                if ((m = input.match(regexp))) {
                    lines = m[0].match(/\n.*/g);
                    if (lines) {
                        self.lineNumber += lines.length;
                    }
                    lib.mix(self, {
                        firstLine: self.lastLine,
                        lastLine: self.lineNumber + 1,
                        firstColumn: self.lastColumn,
                        lastColumn: lines ? lines[lines.length - 1].length - 1 : self.lastColumn + m[0].length
                    });
                    var match;
                    // for error report
                    match = self.match = m[0];

                    // all matches
                    self.matches = m;
                    // may change by user
                    self.text = match;
                    // matched content utils now
                    self.matched += match;
                    ret = action && action.call(self);
                    if (ret === undefined) {
                        ret = token;
                    } else {
                        ret = self.mapSymbol(ret);
                    }
                    input = input.slice(match.length);
                    self.input = input;

                    if (ret) {
                        return ret;
                    } else {
                        // ignore
                        return self.lex();
                    }
                }
            }

            lib.error("lex error at line " + self.lineNumber + ":\n" + self.showDebugInfo());
            return undefined;
        }
    };
    Lexer.STATIC = {
        'INITIAL': 'I',
        'DEBUG_CONTEXT_LIMIT': 20,
        'END_TAG': '$EOF'
    };
    var lexer = new Lexer({
        'rules': [
            [2, /^"(\\"|\\\\|\\\/|\\b|\\f|\\n|\\r|\\t|\\u[0-9a-zA-Z]{4}|[^\\"\x00-\x1f])*"/, 0],
            [0, /^[\t\r\n\x20]/, 0],
            [3, /^,/, 0],
            [4, /^:/, 0],
            [5, /^\[/, 0],
            [6, /^\]/, 0],
            [7, /^\{/, 0],
            [8, /^\}/, 0],
            [9, /^-?\d+(?:\.\d+)?(?:e-?\d+)?/i, 0],
            [10, /^true|false/, 0],
            [11, /^null/, 0],
            [12, /^./, 0]
        ]
    });
    parser.lexer = lexer;
    lexer.symbolMap = {
        '$EOF': 1,
        'STRING': 2,
        'COMMA': 3,
        'COLON': 4,
        'LEFT_BRACKET': 5,
        'RIGHT_BRACKET': 6,
        'LEFT_BRACE': 7,
        'RIGHT_BRACE': 8,
        'NUMBER': 9,
        'BOOLEAN': 10,
        'NULL': 11,
        'INVALID': 12,
        '$START': 13,
        'json': 14,
        'value': 15,
        'object': 16,
        'array': 17,
        'elementList': 18,
        'member': 19,
        'memberList': 20
    };
    parser.productions = [
        [13, [14]],
        [14, [15], function () {
            return this.$1;
        }],
        [15, [2], function () {
            return this.yy.unQuote(this.$1);
        }],
        [15, [9], function () {
            return parseFloat(this.$1);
        }],
        [15, [16], function () {
            return this.$1;
        }],
        [15, [17], function () {
            return this.$1;
        }],
        [15, [10], function () {
            return this.$1 === 'true';
        }],
        [15, [11], function () {
            return null;
        }],
        [18, [15], function () {
            return [this.$1];
        }],
        [18, [18, 3, 15], function () {
            this.$1[this.$1.length] = this.$3;
            return this.$1;
        }],
        [17, [5, 6], function () {
            return [];
        }],
        [17, [5, 18, 6], function () {
            return this.$2;
        }],
        [19, [2, 4, 15], function () {
            return {
                key: this.yy.unQuote(this.$1),
                value: this.$3
            };
        }],
        [20, [19], function () {
            var ret = {};
            ret[this.$1.key] = this.$1.value;
            return ret;
        }],
        [20, [20, 3, 19], function () {
            this.$1[this.$3.key] = this.$3.value;
            return this.$1;
        }],
        [16, [7, 8], function () {
            return {};
        }],
        [16, [7, 20, 8], function () {
            return this.$2;
        }]
    ];
    parser.table = {
        'gotos': {
            '0': {
                '14': 7,
                '15': 8,
                '16': 9,
                '17': 10
            },
            '2': {
                '15': 12,
                '16': 9,
                '17': 10,
                '18': 13
            },
            '3': {
                '19': 16,
                '20': 17
            },
            '18': {
                '15': 23,
                '16': 9,
                '17': 10
            },
            '20': {
                '15': 24,
                '16': 9,
                '17': 10
            },
            '21': {
                '19': 25
            }
        },
        'action': {
            '0': {
                '2': [1, 0, 1],
                '5': [1, 0, 2],
                '7': [1, 0, 3],
                '9': [1, 0, 4],
                '10': [1, 0, 5],
                '11': [1, 0, 6]
            },
            '1': {
                '1': [2, 2, 0],
                '3': [2, 2, 0],
                '6': [2, 2, 0],
                '8': [2, 2, 0]
            },
            '2': {
                '2': [1, 0, 1],
                '5': [1, 0, 2],
                '6': [1, 0, 11],
                '7': [1, 0, 3],
                '9': [1, 0, 4],
                '10': [1, 0, 5],
                '11': [1, 0, 6]
            },
            '3': {
                '2': [1, 0, 14],
                '8': [1, 0, 15]
            },
            '4': {
                '1': [2, 3, 0],
                '3': [2, 3, 0],
                '6': [2, 3, 0],
                '8': [2, 3, 0]
            },
            '5': {
                '1': [2, 6, 0],
                '3': [2, 6, 0],
                '6': [2, 6, 0],
                '8': [2, 6, 0]
            },
            '6': {
                '1': [2, 7, 0],
                '3': [2, 7, 0],
                '6': [2, 7, 0],
                '8': [2, 7, 0]
            },
            '7': {
                '1': [0, 0, 0]
            },
            '8': {
                '1': [2, 1, 0]
            },
            '9': {
                '1': [2, 4, 0],
                '3': [2, 4, 0],
                '6': [2, 4, 0],
                '8': [2, 4, 0]
            },
            '10': {
                '1': [2, 5, 0],
                '3': [2, 5, 0],
                '6': [2, 5, 0],
                '8': [2, 5, 0]
            },
            '11': {
                '1': [2, 10, 0],
                '3': [2, 10, 0],
                '6': [2, 10, 0],
                '8': [2, 10, 0]
            },
            '12': {
                '3': [2, 8, 0],
                '6': [2, 8, 0]
            },
            '13': {
                '3': [1, 0, 18],
                '6': [1, 0, 19]
            },
            '14': {
                '4': [1, 0, 20]
            },
            '15': {
                '1': [2, 15, 0],
                '3': [2, 15, 0],
                '6': [2, 15, 0],
                '8': [2, 15, 0]
            },
            '16': {
                '3': [2, 13, 0],
                '8': [2, 13, 0]
            },
            '17': {
                '3': [1, 0, 21],
                '8': [1, 0, 22]
            },
            '18': {
                '2': [1, 0, 1],
                '5': [1, 0, 2],
                '7': [1, 0, 3],
                '9': [1, 0, 4],
                '10': [1, 0, 5],
                '11': [1, 0, 6]
            },
            '19': {
                '1': [2, 11, 0],
                '3': [2, 11, 0],
                '6': [2, 11, 0],
                '8': [2, 11, 0]
            },
            '20': {
                '2': [1, 0, 1],
                '5': [1, 0, 2],
                '7': [1, 0, 3],
                '9': [1, 0, 4],
                '10': [1, 0, 5],
                '11': [1, 0, 6]
            },
            '21': {
                '2': [1, 0, 14]
            },
            '22': {
                '1': [2, 16, 0],
                '3': [2, 16, 0],
                '6': [2, 16, 0],
                '8': [2, 16, 0]
            },
            '23': {
                '3': [2, 9, 0],
                '6': [2, 9, 0]
            },
            '24': {
                '3': [2, 12, 0],
                '8': [2, 12, 0]
            },
            '25': {
                '3': [2, 14, 0],
                '8': [2, 14, 0]
            }
        }
    };
    parser.parse = function parse(input) {

        var self = this,
            lexer = self.lexer,
            state,
            symbol,
            action,
            table = self.table,
            gotos = table.gotos,
            tableAction = table.action,
            productions = self.productions,
            valueStack = [null],
            stack = [0];

        lexer.resetInput(input);

        while (1) {
            // retrieve state number from top of stack
            state = stack[stack.length - 1];

            if (!symbol) {
                symbol = lexer.lex();
            }

            if (!symbol) {
                lib.log("it is not a valid input: " + input, "error");
                return false;
            }

            // read action for current state and first input
            action = tableAction[state] && tableAction[state][symbol];

            if (!action) {
                var expected = [],
                    error;
                if (tableAction[state]) {
                    lib.each(tableAction[state], function (_, key) {	// jshint ignore: line
                        expected.push(self.lexer.mapReverseSymbol(key));
                    });
                }
                error = "Syntax error at line " + lexer.lineNumber + ":\n" + lexer.showDebugInfo() + '\n' + "expect " + expected.join(", ");
                lib.log(error);
                return false;
            }

            switch (action[GrammarConst.TYPE_INDEX]) {

                case GrammarConst.SHIFT_TYPE:

                    stack.push(symbol);

                    valueStack.push(lexer.text);

                    // push state
                    stack.push(action[GrammarConst.TO_INDEX]);

                    // allow to read more
                    symbol = null;

                    break;

                case GrammarConst.REDUCE_TYPE:

                    var production = productions[action[GrammarConst.PRODUCTION_INDEX]],
                        reducedSymbol = production.symbol || production[0],
                        reducedAction = production.action || production[2],
                        reducedRhs = production.rhs || production[1],
                        len = reducedRhs.length,
                        i = 0,
                        ret,
                        $$ = valueStack[valueStack.length - len]; // default to $$ = $1

                    self.$$ = $$;

                    ret = undefined;

                    for (; i < len; i++) {
                        self["$" + (len - i)] = valueStack[valueStack.length - 1 - i];
                    }

                    if (reducedAction) {
                        ret = reducedAction.call(self);
                    }

                    if (ret !== undefined) {
                        $$ = ret;
                    } else {
                        $$ = self.$$;
                    }

                    if (len) {
                        stack = stack.slice(0, -1 * len * 2);
                        valueStack = valueStack.slice(0, -1 * len);
                    }

                    stack.push(reducedSymbol);

                    valueStack.push($$);

                    var newState = gotos[stack[stack.length - 2]][stack[stack.length - 1]];

                    stack.push(newState);

                    break;

                case GrammarConst.ACCEPT_TYPE:

                    return $$;
            }

        }
    };

    // json/parse
    function walk(holder, name, reviver) {
        var val = holder[name],
            i, len, newElement;

        if (typeof val === 'object') {
            if (lib.isArray(val)) {
                i = 0;
                len = val.length;
                var newVal = [];
                while (i < len) {
                    newElement = walk(val, String(i), reviver);
                    if (newElement !== undefined) {
                        newVal[newVal.length] = newElement;
                    }
                }
                val = newVal;
            } else {
                var keys = lib.keys(val);
				i = 0;
                for (len = keys.length; i < len; i++) {
                    var p = keys[i];
                    newElement = walk(val, p, reviver);
                    if (newElement === undefined) {
                        delete val[p];
                    } else {
                        val[p] = newElement;
                    }
                }
            }
        }

        return reviver.call(holder, name, val);
    }

    lib.parse = function (str, reviver) {	
        var root = parser.parse(String(str));
        if (reviver) {
            return walk({
                '': root
            }, '', reviver);
        } else {
            return root;
        }
    };

})(Dynamsoft.Lib);
/// File Description:
/// 	All polyfills would be put here.
///

(function (lib) {
    "use strict";

    var _array_ver = 20200521;
    if (lib._array_ver) {
        if (lib._array_ver >= _array_ver) {
            return;
        }
    }
    lib._array_ver = _array_ver;
	
    // array.indexof
    var AP = Array.prototype,
        indexOf = AP.indexOf,
        filter = AP.filter;

    // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Array/indexOf
    // Production steps of ECMA-262, Edition 5, 15.4.4.14
    // Reference: http://es5.github.io/#x15.4.4.14
    if (!lib.isFunction(indexOf)) {
        indexOf = function (searchElement, fromIndex) {

            var k;

            // 1. Let o be the result of calling ToObject passing
            //    the this value as the argument.
            if (this == null) {
                return -1;
            }

            var o = Object(this);

            // 2. Let lenValue be the result of calling the Get
            //    internal method of o with the argument "length".
            // 3. Let len be ToUint32(lenValue).
            var len = o.length >>> 0;

            // 4. If len is 0, return -1.
            if (len === 0) {
                return -1;
            }

            // 5. If argument fromIndex was passed let n be
            //    ToInteger(fromIndex); else let n be 0.
            var n = +fromIndex || 0;

            if (Math.abs(n) === Infinity) {
                n = 0;
            }

            // 6. If n >= len, return -1.
            if (n >= len) {
                return -1;
            }

            // 7. If n >= 0, then Let k be n.
            // 8. Else, n<0, Let k be len - abs(n).
            //    If k is less than 0, then let k be 0.
            k = Math.max(n >= 0 ? n : len - Math.abs(n), 0);

            // 9. Repeat, while k < len
            while (k < len) {
                // a. Let Pk be ToString(k).
                //   This is implicit for LHS operands of the in operator
                // b. Let kPresent be the result of calling the
                //    HasProperty internal method of o with argument Pk.
                //   This step can be combined with c
                // c. If kPresent is true, then
                //    i.  Let elementK be the result of calling the Get
                //        internal method of o with the argument ToString(k).
                //   ii.  Let same be the result of applying the
                //        Strict Equality Comparison Algorithm to
                //        searchElement and elementK.
                //  iii.  If same is true, return k.
                if (k in o && o[k] === searchElement) {
                    return k;
                }
                k++;
            }
            return -1;
        };
    }
	
    lib.mix(lib, {

        filter: filter ?
            function (arr, fn, context) {
                return filter.call(arr, fn, context || this);
            } :
            function (arr, fn, context) {
                var ret = [];
                lib.each(arr, function (item, i, arr) {
                    if (fn.call(context || this, item, i, arr)) {
                        ret.push(item);
                    }
                });
                return ret;
            },
        indexOf: function (item, arr) {
            return indexOf.call(arr, item);
        },

		uniq: function (ary){
			var tmp = [],
				len = ary.length;
			//var index = [];
			for(var i = 0; i < len; i++) {
				for(var j = i + 1; j < len; j++){
					if (ary[i] === ary[j]){
						i++;
						j = i;
					}
				}
				tmp.push(ary[i]);
				//index.push(i);
			}
			return tmp;
		}
    });
})(Dynamsoft.Lib);
/// File Description:
/// 	All polyfills would be put here.
///

(function (lib) {
    "use strict";

    var _function_ver = 20200521;
    if (lib._function_ver) {
        if (lib._function_ver >= _function_ver) {
            return;
        }
    }
    lib._function_ver = _function_ver;
	
    var AP = Array.prototype,
		FP = Function.prototype;

    // Enhanced Browser
    if (!lib.isFunction(FP.bind)) {
        FP.bind = function (context) {

            var self = this;
            if (1 < arguments.length) {
                // extra arguments to send by default
                var _args = AP.slice.call(arguments, 1);
                return function () {
                    return self.apply(
                        context,
                        arguments.length ?
                            // concat arguments with those received
                            _args.concat(AP.slice.call(arguments)) :
                            // send just arguments, no concat, no slice
                            _args
                    );
                };
            }
            return function () {
                return arguments.length ? self.apply(context, arguments) : self.call(context);
            };
        };
    }

})(Dynamsoft.Lib);
/// 
/// 	String.trim()
///
(function (lib) {
    "use strict";

    var _string_ver = 20200521;
    if (lib._string_ver) {
        if (lib._string_ver >= _string_ver) {
            return;
        }
    }
    lib._string_ver = _string_ver;
	
	var RE_TRIM = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g,
		StringP = String.prototype,
		EMPTY_STR = '',
		trim = StringP.trim;

	// string.trim
	// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String/trim
	if (!trim) {
		trim = StringP.trim = function () {
			return this.replace(RE_TRIM, EMPTY_STR);
		};
	}

	lib.trim = function (str) {
		return str == null ? EMPTY_STR : trim.call(str);
	};
})(Dynamsoft.Lib);
(function (lib, nil) {

    "use strict";

    // IE doesn't include non-breaking-space (0xa0) in their \s character
    // class (as required by section 7.2 of the ECMAScript spec), we explicitly
    // include it in the regexp to enforce consistent cross-browser behavior.
	
    var EMPTY_STR = '',
        FALSE = !1, TRUE = !0,
		logger = lib.getLogger(),
        isDef = lib.isDef,
		each = lib.each,
		
        SEP = '&',
        EQ = '=',
        HEX_BASE = 16,
        // http://www.owasp.org/index.php/XSS_(Cross_Site_Scripting)_Prevention_Cheat_Sheet
        // http://wonko.com/post/html-escaping
        htmlEntities = {
            '&amp;': '&',
            '&gt;': '>',
            '&lt;': '<',
            '&#x60;': '`',
            '&#x2F;': '/',
            '&quot;': '"',
            /*jshint quotmark:false*/
            '&#x27;': "'"
        },
        reverseEntities = {},
        escapeReg,
        unEscapeReg,
        // - # $ ^ * ( ) + [ ] { } | \ , . ?
        escapeRegExp = /[\-#$\^*()+\[\]{}|\\,.?\s]/g;
		
	each(htmlEntities, function (item, k) {
		reverseEntities[item] = k;
	});
	
    function isValidParamValue(val) {
        var t = typeof val;
        // If the type of val is null, undefined, number, string, boolean, return TRUE.
        return val == null || (t !== 'object' && t !== 'function');
    }

    function getEscapeReg() {
        if (escapeReg) {
            return escapeReg;
        }
        var str = EMPTY_STR;
        each(htmlEntities, function (entity) {
            str += entity + '|';
        });
        str = str.slice(0, -1);
        escapeReg = new RegExp(str, 'g');
        return escapeReg;
    }

    function getUnEscapeReg() {
        if (unEscapeReg) {
            return unEscapeReg;
        }
        var str = EMPTY_STR;
        each(reverseEntities, function (entity) {
            str += entity + '|';
        });
        str += '&#(\\d{1,5});';
        unEscapeReg = new RegExp(str, 'g');
        return unEscapeReg;
    }
	
	function _urlEncode (s) {
		return encodeURIComponent(String(s));
	}
	
    lib.mix(lib, {

        /**
         * Call encodeURIComponent to encode a url component
         * @param {String} s part of url to be encoded.
         * @return {String} encoded url part string.
         */
        urlEncode: _urlEncode,

        /**
         * Call decodeURIComponent to decode a url component
         * and replace '+' with space.
         * @param {String} s part of url to be decoded.
         * @return {String} decoded url part string.
         */
        urlDecode: function (s) {
            return decodeURIComponent(s.replace(/\+/g, ' '));
        },

        /**
         * frequently used in taobao cookie about nick
         * @return {String} un-unicode string.
         */
        fromUnicode: function (str) {
            return str.replace(/\\u([a-f\d]{4})/ig, function (m, u) {
                return String.fromCharCode(parseInt(u, HEX_BASE));
            });
        },
        /**
         * get escaped string from html.
         * only escape
         *      & > < ` / " '
         * refer:
         *
         * [http://yiminghe.javaeye.com/blog/788929](http://yiminghe.javaeye.com/blog/788929)
         *
         * [http://wonko.com/post/html-escaping](http://wonko.com/post/html-escaping)
         * @param str {string} text2html show
         * @return {String} escaped html
         */
        escapeHtml: function (str) {
            return (str + '').replace(getEscapeReg(), function (m) {
                return reverseEntities[m];
            });
        },

        /**
         * get escaped regexp string for construct regexp.
         * @param str
         * @return {String} escaped regexp
         */
        escapeRegExp: function (str) {
            return str.replace(escapeRegExp, '\\$&');
        },

        /**
         * un-escape html to string.
         * only unescape
         *      &amp; &lt; &gt; &#x60; &#x2F; &quot; &#x27; &#\d{1,5}
         * @param str {string} html2text
         * @return {String} un-escaped html
         */
        unEscapeHtml: function (str) {
            return str.replace(getUnEscapeReg(), function (m, n) {
                return htmlEntities[m] || String.fromCharCode(+n);
            });
        },
        /**
         * Creates a serialized string of an array or object.
         *
         * for example:
         *     @example
         *     {foo: 1, bar: 2}    // -> 'foo=1&bar=2'
         *     {foo: 1, bar: [2, 3]}    // -> 'foo=1&bar=2&bar=3'
         *     {foo: '', bar: 2}    // -> 'foo=&bar=2'
         *     {foo: undefined, bar: 2}    // -> 'foo=undefined&bar=2'
         *     {foo: TRUE, bar: 2}    // -> 'foo=TRUE&bar=2'
         *
         * @param {Object} o json data
         * @param {String} [sep='&'] separator between each pair of data
         * @param {String} [eq='='] separator between key and value of data
         * @param {Boolean} [serializeArray=true] whether add '[]' to array key of data
         * @return {String}
         */
        param: function (o, sep, eq, serializeArray) {
            sep = sep || SEP;
            eq = eq || EQ;
            if (lib.isUndef(serializeArray)) {
                serializeArray = TRUE;
            }
			
            var buf = [];

			each(o, function(val, k){
				
				var key = _urlEncode(k);

                // val is valid non-array value
                if (isValidParamValue(val)) {
                    buf.push(key);
                    if (isDef(val)) {
                        buf.push(eq, _urlEncode(val + EMPTY_STR));
                    }
                    buf.push(sep);
                }
                // val is not empty array
                else if (lib.isArray(val) && val.length) {
					
					each(val, function(v){
					
                        if (isValidParamValue(v)) {
                            buf.push(key, (serializeArray ? _urlEncode('[]') : EMPTY_STR));
                            if (isDef(v)) {
                                buf.push(eq, _urlEncode(v + EMPTY_STR));
                            }
                            buf.push(sep);
                        }
                    
					});
                }
                // ignore other cases, including empty array, Function, RegExp, Date etc.
			});
			
            buf.pop();
            return buf.join(EMPTY_STR);
        },

        /**
         * Parses a URI-like query string and returns an object composed of parameter/value pairs.
         *
         * for example:
         *      @example
         *      'section=blog&id=45'        // -> {section: 'blog', id: '45'}
         *      'section=blog&tag=js&tag=doc' // -> {section: 'blog', tag: ['js', 'doc']}
         *      'tag=ruby%20on%20rails'        // -> {tag: 'ruby on rails'}
         *      'id=45&raw'        // -> {id: '45', raw: ''}
         * @param {String} str param string
         * @param {String} [sep='&'] separator between each pair of data
         * @param {String} [eq='='] separator between key and value of data
         * @return {Object} json data
         */
        unparam: function (str, sep, eq) {
            if (!lib.isString(str) || !(str = lib.trim(str))) {
                return {};
            }
            sep = sep || SEP;
            eq = eq || EQ;
            var ret = {},
                eqIndex,
                decode = lib.urlDecode,
                pairs = str.split(sep),
                key, val,
                i = 0, len = pairs.length;

            for (; i < len; ++i) {
                eqIndex = lib.indexOf(eq, pairs[i]);
                if (eqIndex === -1) {
                    key = decode(pairs[i]);
                    val = nil;
                } else {
                    // remember to decode key!
                    key = decode(pairs[i].substring(0, eqIndex));
                    val = pairs[i].substring(eqIndex + 1);
                    try {
                        val = decode(val);
                    } catch (e) {
                        logger.error('decodeURIComponent error : ' + val);
                        logger.error(e);
                    }
                    if (lib.endsWith(key, '[]')) {
                        key = key.substring(0, key.length - 2);
                    }
                }
                if (key in ret) {
                    if (lib.isArray(ret[key])) {
                        ret[key].push(val);
                    } else {
                        ret[key] = [ret[key], val];
                    }
                } else {
                    ret[key] = val;
                }
            }
            return ret;
        }
    });

})(Dynamsoft.Lib);(function (lib) {

    "use strict";

    /*
     Refer
     - https://github.com/joyent/node/blob/master/lib/path.js
     */
    // [root, dir, basename, ext]
    var splitPathRe = /^(\/?)([\s\S]+\/(?!$)|\/)?((?:\.{1,2}$|[\s\S]+?)?(\.[^.\/]*)?)$/;

	// resolves . and .. elements in a path array with directory names there
	// must be no slashes or device names (c:\) in the array
	// (so also no leading and trailing slashes - it does not distinguish
	// relative and absolute paths)
	function normalizeArray(parts, allowAboveRoot) {
		var res = [];
		for (var i = 0; i < parts.length; i++) {
			var p = parts[i];

			// ignore empty parts
			if (!p || p === '.')
			continue;

			if (p === '..') {
				if (res.length && res[res.length - 1] !== '..') {
					res.pop();
				} else if (allowAboveRoot) {
					res.push('..');
				}
			} else {
				res.push(p);
			}
		}

		return res;
	}

    /**
     * Path Utils.
     * @singleton
     */
    var Path = lib.Path = {
        /**
         * resolve([from ...], to)
         * @return {String} Resolved path.
         */
        resolve: function () {
            var resolvedPath = '',
                resolvedPathStr,
                i,
                args = (arguments),
                path,
                absolute = 0;

            for (i = args.length - 1; i >= 0 && !absolute; i--) {
                path = args[i];
                // path is not empty string
                if (lib.isString(path) && !!path) {
                    resolvedPath = path + '/' + resolvedPath;
                    absolute = path.charAt(0) === '/';
                }
            }

            resolvedPathStr = normalizeArray(lib.filter(resolvedPath.split('/'), function (p) {
                return !!p;
            }), !absolute).join('/');

            return ((absolute ? '/' : '') + resolvedPathStr) || '.';
        },

        /**
         * normalize .. and . in path
         * @param {String} path Path tobe normalized
         *
         *
         *      'x/y/../z' => 'x/z'
         *      'x/y/z/../' => 'x/y/'
         *
         * @return {String}
         */
        normalize: function (path) {
            var absolute = path.charAt(0) === '/',
                trailingSlash = path.slice(-1) === '/';

            path = normalizeArray(lib.filter(path.split('/'), function (p) {
                return !!p;
            }), !absolute).join('/');

            if (!path && !absolute) {
                path = '.';
            }

            if (path && trailingSlash) {
                path += '/';
            }


            return (absolute ? '/' : '') + path;
        },

        /**
         * join([path ...]) and normalize
         * @return {String}
         */
        join: function () {
            var args = lib.makeArray(arguments);
            return Path.normalize(lib.filter(args, function (p) {
                return p && (lib.isString(p));
            }).join('/'));
        },

        /**
         * Get string which is to relative to from
         * @param {String} from
         * @param {String} to
         *
         *
         *      relative('x/','x/y/z') => 'y/z'
         *      relative('x/t/z','x/') => '../../'
         *
         * @return {String}
         */
        relative: function (from, to) {
            from = Path.normalize(from);
            to = Path.normalize(to);

            var fromParts = lib.filter(from.split('/'), function (p) {
                return !!p;
            }),
                path = [],
                sameIndex,
                sameIndex2,
                toParts = lib.filter(to.split('/'), function (p) {
                    return !!p;
                }), commonLength = Math.min(fromParts.length, toParts.length);

            for (sameIndex = 0; sameIndex < commonLength; sameIndex++) {
                if (fromParts[sameIndex] !== toParts[sameIndex]) {
                    break;
                }
            }

            sameIndex2 = sameIndex;

            while (sameIndex < fromParts.length) {
                path.push('..');
                sameIndex++;
            }

            path = path.concat(toParts.slice(sameIndex2));

            return path.join('/');
        },

        /**
         * Get base name of path
         * @param {String} path
         * @param {String} [ext] ext to be stripped from result returned.
         * @return {String}
         */
        basename: function (path, ext) {
            var result = path.match(splitPathRe) || [],
                basename;
            basename = result[3] || '';
            if (ext && basename && basename.slice(-1 * ext.length) === ext) {
                basename = basename.slice(0, -1 * ext.length);
            }
            return basename;
        },

        /**
         * Get dirname of path
         * @param {String} path
         * @return {String}
         */
        dirname: function (path) {
            var result = path.match(splitPathRe) || [],
                root = result[1] || '',
                dir = result[2] || '';

            if (!root && !dir) {
                // No dirname
                return '.';
            }

            if (dir) {
                // It has a dirname, strip trailing slash
                dir = dir.substring(0, dir.length - 1);
            }

            return root + dir;
        },

        /**
         * Get extension name of file in path
         * @param {String} path
         * @return {String}
         */
        extname: function (path) {
            return (path.match(splitPathRe) || [])[4] || '';
        }
    };
})(Dynamsoft.Lib);(function (lib, nil) {

    "use strict";

    function parseQuery(self) {
        if (!self._queryMap) {
            self._queryMap = lib.unparam(self._query);
        }
    }

    /**
     * @class uriQuery
     * Query data structure.
     * @param {String} [query] encoded query string(without question mask).
     */
    function uriQuery(query) {
        this._query = query || ''; // jshint ignore:line
    }

    uriQuery.prototype = {
        constructor: uriQuery,

        /**
         * Cloned new instance.
         * @return {uriQuery}
         */
        clone: function () {
            return new uriQuery(this.toString());
        },


        /**
         * reset to a new query string
         * @param {String} query
         * @chainable
         */
        reset: function (query) {
            var self = this;
            self._query = query || '';
            self._queryMap = null;
            return self;
        },

        /**
         * Parameter count.
         * @return {Number}
         */
        count: function () {
            var self = this,
                count = 0;
				
            parseQuery(self);
			lib.each(self._queryMap, function (item) {
                if (lib.isArray(item)) {
                    count += item.length;
                } else {
                    count++;
                }
			});
			
            return count;
        },

        /**
         * judge whether has query parameter
         * @param {String} [key]
         */
        has: function (key) {
            var self = this, _queryMap;
            parseQuery(self);
            _queryMap = self._queryMap;
            if (key) {
                return key in _queryMap;
            } else {
                return !lib.isEmptyObject(_queryMap);
            }
        },

        /**
         * Return parameter value corresponding to current key
         * @param {String} [key]
         */
        get: function (key) {
            var self = this, _queryMap;
            parseQuery(self);
            _queryMap = self._queryMap;
            if (key) {
                return _queryMap[key];
            } else {
                return _queryMap;
            }
        },

        /**
         * Parameter names.
         * @return {String[]}
         */
        keys: function () {
            var self = this;
            parseQuery(self);
            return lib.keys(self._queryMap);
        },

        /**
         * Set parameter value corresponding to current key
         * @param {String} key
         * @param value
         * @chainable
         */
        set: function (key, value) {
            var self = this, _queryMap;
            parseQuery(self);
            _queryMap = self._queryMap;
            if (lib.isString(key)) {
                self._queryMap[key] = value;
            } else {
                if (key instanceof uriQuery) {
                    key = key.get();
                }
                lib.each(key, function (v, k) {
                    _queryMap[k] = v;
                });
            }
            return self;
        },

        /**
         * Remove parameter with specified name.
         * @param {String} key
         * @chainable
         */
        remove: function (key) {
            var self = this;
            parseQuery(self);
            if (key) {
                delete self._queryMap[key];
            } else {
                self._queryMap = {};
            }
            return self;

        },

        /**
         * Add parameter value corresponding to current key
         * @param {String} key
         * @param value
         * @chainable
         */
        add: function (key, value) {
            var self = this,
                _queryMap,
                currentValue;
            if (lib.isString(key)) {
                parseQuery(self);
                _queryMap = self._queryMap;
                currentValue = _queryMap[key];
                if (lib.isUndef(currentValue)) {
                    currentValue = value;
                } else {
                    currentValue = [].concat(currentValue).concat(value);
                }
                _queryMap[key] = currentValue;
            } else {
                if (key instanceof uriQuery) {
                    key = key.get();
                }
				
				lib.each(key, function (item, k) {
                    self.add(k, item);
                });
            }
            return self;
        },

        /**
         * Serialize query to string.
         * @param {Boolean} [serializeArray=true]
         * whether append [] to key name when value 's type is array
         */
        toString: function (serializeArray) {
            var self = this;
            parseQuery(self);
            return lib.param(self._queryMap, nil, nil, serializeArray);
        }
    };

    lib.uriQuery = uriQuery;
	
})(Dynamsoft.Lib);
(function (lib) {

    "use strict";

    var uriQuery = lib.uriQuery,
		each = lib.each,
		Path = lib.Path,
		logger = lib.getLogger(),

		reDisallowedInSchemeOrUserInfo = /[#\/\?@]/g,
        reDisallowedInPathName = /[#\?]/g,
        reDisallowedInQuery = /[#@]/g,
        reDisallowedInFragment = /#/g,

        REG_INFO = {
            scheme: 1,
            userInfo: 2,
            hostname: 3,
            port: 4,
            path: 5,
            query: 6,
            fragment: 7
        },
        URI_SPLIT_REG = new RegExp(
            '^' +
            /*
             Scheme names consist of a sequence of characters beginning with a
             letter and followed by any combination of letters, digits, plus
             ('+'), period ('.'), or hyphen ('-').
             */
            '(?:([\\w\\d+.-]+):)?' + // scheme

            '(?://' +
            /*
             The authority component is preceded by a double slash ('//') and is
             terminated by the next slash ('/'), question mark ('?'), or number
             sign ('#') character, or by the end of the URI.
             */
            '(?:([^/?#@]*)@)?' + // userInfo

            '(' +
            '[\\w\\d\\-\\u0100-\\uffff.+%]*' +
            '|' +
            // ipv6
            '\\[[^\\]]+\\]' +
            ')' + // hostname - restrict to letters,
            // digits, dashes, dots, percent
            // escapes, and unicode characters.
            '(?::([0-9]+))?' + // port
            ')?' +
            /*
             The path is terminated
             by the first question mark ('?') or number sign ('#') character, or
             by the end of the URI.
             */
            '([^?#]+)?' + // path. hierarchical part
            /*
             The query component is indicated by the first question
             mark ('?') character and terminated by a number sign ('#') character
             or by the end of the URI.
             */
            '(?:\\?([^#]*))?' + // query. non-hierarchical data
            /*
             The fragment identifier component of a URI allows indirect
             identification of a secondary resource by reference to a primary
             resource and additional identifying information.

             A
             fragment identifier component is indicated by the presence of a
             number sign ('#') character and terminated by the end of the URI.
             */
            '(?:#(.*))?' + // fragment
            '$');

    function padding2(str) {
        return str.length === 1 ? '0' + str : str;
    }

    function equalsIgnoreCase(str1, str2) {
        return str1.toLowerCase() === str2.toLowerCase();
    }


    // www.ta#bao.com // => www.ta.com/#bao.com
    // www.ta%23bao.com
    // Percent-Encoding
    function encodeSpecialChars(str, specialCharsReg) {
        // encodeURI( ) is intended to encode complete URIs,
        // the following ASCII punctuation characters,
        // which have special meaning in URIs, are not escaped either:
        // ; / ? : @ & = + $ , #
        return encodeURI(str).replace(specialCharsReg, function (m) {
            return '%' + padding2(m.charCodeAt(0).toString(16));
        });
    }

    /**
     * @class Uri
     * Most of its interfaces are same with window.location.
     * @param {String|Uri} [uriStr] Encoded uri string.
     */
    function Uri(uriStr) {

        if (uriStr instanceof Uri) {
            return uriStr.clone();
        }

        var components, self = this;

        lib.mix(self,
            {
                /**
                 * scheme such as 'http:'. aka protocol without colon
                 * @type {String}
                 */
                scheme: '',
                /**
                 * User credentials such as 'yiminghe:gmail'
                 * @type {String}
                 */
                userInfo: '',
                /**
                 * hostname such as 'docs.kissyui.com'. aka domain
                 * @type {String}
                 */
                hostname: '',
                /**
                 * Port such as '8080'
                 * @type {String}
                 */
                port: '',
                /**
                 * path such as '/index.htm'. aka pathname
                 * @type {String}
                 */
                path: '',
                /**
                 * uriQuery object for search string. aka search
                 * @type {uriQuery}
                 */
                query: '',
                /**
                 * fragment such as '#!/test/2'. aka hash
                 */
                fragment: ''
            });

        components = Uri.getComponents(uriStr);

        each(components, function (v, key) {
            v = v || '';
            if (key === 'query') {
                // need encoded content
                self.query = new uriQuery(v);
            } else {
                // https://github.com/kissyteam/kissy/issues/298
                try {
                    v = lib.urlDecode(v);
                } catch (e) {
                    logger.error(e + 'urlDecode error : ' + v);
                }
                // need to decode to get data structure in memory
                self[key] = v;
            }
        });

        return self;
    }

    Uri.prototype = {
        constructor: Uri,

        /**
         * Return a cloned new instance.
         * @return {Uri}
         */
        clone: function () {
            var uri = new Uri(), self = this;
            each(REG_INFO, function (index, key) {
                uri[key] = self[key];
            });
            uri.query = uri.query.clone();
            return uri;
        },


        /**
         * The reference resolution algorithm.rfc 5.2
         * return a resolved uri corresponding to current uri
         * @param {Uri|String} relativeUri
         *
         * for example:
         *      @example
         *      this: 'http://y/yy/z.com?t=1#v=2'
         *      'https:/y/' => 'https:/y/'
         *      '//foo' => 'http://foo'
         *      'foo' => 'http://y/yy/foo'
         *      '/foo' => 'http://y/foo'
         *      '?foo' => 'http://y/yy/z.com?foo'
         *      '#foo' => http://y/yy/z.com?t=1#foo'
         *
         * @return {Uri}
         */
        resolve: function (relativeUri) {

            if (lib.isString(relativeUri)) {
                relativeUri = new Uri(relativeUri);
            }

            var self = this,
                override = 0,
                lastSlashIndex,
                order = ['scheme', 'userInfo', 'hostname', 'port', 'path', 'query', 'fragment'],
                target = self.clone();

            each(order, function (o) {
                if (o === 'path') {
                    // relativeUri does not set for scheme/userInfo/hostname/port
                    if (override) {
                        target[o] = relativeUri[o];
                    } else {
                        var path = relativeUri.path;
                        if (path) {
                            // force to override target 's query with relative
                            override = 1;
                            if (!lib.startsWith(path, '/')) {
                                if (target.hostname && !target.path) {
                                    // RFC 3986, section 5.2.3, case 1
                                    path = '/' + path;
                                } else if (target.path) {
                                    // RFC 3986, section 5.2.3, case 2
                                    lastSlashIndex = target.path.lastIndexOf('/');
                                    if (lastSlashIndex !== -1) {
                                        path = target.path.slice(0, lastSlashIndex + 1) + path;
                                    }
                                }
                            }
                            // remove .. / .  as part of the resolution process
                            target.path = Path.normalize(path);
                        }
                    }
                } else if (o === 'query') {
                    if (override || relativeUri.query.toString()) {
                        target.query = relativeUri.query.clone();
                        override = 1;
                    }
                } else if (override || relativeUri[o]) {
                    target[o] = relativeUri[o];
                    override = 1;
                }
            });

            return target;

        },

        /**
         * Get scheme part
         */
        getScheme: function () {
            return this.scheme;
        },

        /**
         * Set scheme part
         * @param {String} scheme
         * @chainable
         */
        setScheme: function (scheme) {
            this.scheme = scheme;
            return this;
        },

        /**
         * Return hostname
         * @return {String}
         */
        getHostname: function () {
            return this.hostname;
        },

        /**
         * Set hostname
         * @param {String} hostname
         * @chainable
         */
        setHostname: function (hostname) {
            this.hostname = hostname;
            return this;
        },

        /**
         * Set user info
         * @param {String} userInfo
         * @chainable
         */
        'setUserInfo': function (userInfo) {
            this.userInfo = userInfo;
            return this;
        },

        /**
         * Get user info
         * @return {String}
         */
        getUserInfo: function () {
            return this.userInfo;
        },

        /**
         * Set port
         * @param {String} port
         * @chainable
         */
        'setPort': function (port) {
            this.port = port;
            return this;
        },

        /**
         * Get port
         * @return {String}
         */
        'getPort': function () {
            return this.port;
        },

        /**
         * Set path
         * @param {string} path
         * @chainable
         */
        setPath: function (path) {
            this.path = path;
            return this;
        },

        /**
         * Get path
         * @return {String}
         */
        getPath: function () {
            return this.path;
        },

        /**
         * Set query
         * @param {String|uriQuery} query
         * @chainable
         */
        'setQuery': function (query) {
            if (lib.isString(query)) {
                if (lib.startsWith(query, '?')) {
                    query = query.slice(1);
                }
                query = new uriQuery(encodeSpecialChars(query, reDisallowedInQuery));
            }
            this.query = query;
            return this;
        },

        /**
         * Get query
         * @return {uriQuery}
         */
        getQuery: function () {
            return this.query;
        },

        /**
         * Get fragment
         * @return {String}
         */
        getFragment: function () {
            return this.fragment;
        },

        /**
         * Set fragment
         * @param {String} fragment
         * @chainable
         */
        'setFragment': function (fragment) {
            var self = this;
            if (lib.startsWith(fragment, '#')) {
                fragment = fragment.slice(1);
            }
            self.fragment = fragment;
            return self;
        },

        /**
         * Judge whether two uri has same domain.
         * @param {Uri} other
         * @return {Boolean}
         */
        isSameOriginAs: function (other) {
            var self = this;
            // port and hostname has to be same
            return equalsIgnoreCase(self.hostname, other.hostname) &&
                equalsIgnoreCase(self.scheme, other.scheme) &&
                equalsIgnoreCase(self.port, other.port);
        },

        /**
         * Serialize to string.
         * See rfc 5.3 Component Recomposition.
         * But kissy does not differentiate between undefined and empty.
         * @param {Boolean} [serializeArray=true]
         * whether append [] to key name when value 's type is array
         * @return {String}
         */
        toString: function (serializeArray) {

            var out = [],
                self = this,
                scheme,
                hostname,
                path,
                port,
                fragment,
                query,
                userInfo;

            if ((scheme = self.scheme)) {
                out.push(encodeSpecialChars(scheme, reDisallowedInSchemeOrUserInfo));
                out.push(':');
            }

            if ((hostname = self.hostname)) {
                out.push('//');
                if ((userInfo = self.userInfo)) {
                    out.push(encodeSpecialChars(userInfo, reDisallowedInSchemeOrUserInfo));
                    out.push('@');
                }

                out.push(encodeURIComponent(hostname));

                if ((port = self.port)) {
                    out.push(':');
                    out.push(port);
                }
            }

            if ((path = self.path)) {
                if (hostname && !lib.startsWith(path, '/')) {
                    path = '/' + path;
                }
                path = Path.normalize(path);
                out.push(encodeSpecialChars(path, reDisallowedInPathName));
            }

            if ((query = (self.query.toString.call(self.query, serializeArray)))) {
                out.push('?');
                out.push(query);
            }

            if ((fragment = self.fragment)) {
                out.push('#');
                out.push(encodeSpecialChars(fragment, reDisallowedInFragment));
            }

            return out.join('');
        }
    };

    Uri.getComponents = function (url) {
		var EMPTY_STR = '';
        url = url || EMPTY_STR;
        var m = url.match(URI_SPLIT_REG) || [],
            ret = {};
        each(REG_INFO, function (index, key) {
            ret[key] = m[index];
        });
        return ret;
    };

    lib.Uri = Uri;
})(Dynamsoft.Lib);/* @preserve
 * The MIT License (MIT)
 * 
 * Copyright (c) 2013-2018 Petka Antonov
 * 
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 * 
 */
(function (dynam, nil) {

	"use strict";
	var lib = dynam.Lib,
		win = lib.win,
		_promise_ver = 20200716;

	if (lib._promise_ver) {
		if (lib.isNumber(lib._promise_ver) && lib._promise_ver >= _promise_ver) {
			return;
		}
	}
	lib._promise_ver = _promise_ver;
	
	if(lib.isFunction(win['__zone_symbol__Promise'])) {
		lib.nativePromise = win['__zone_symbol__Promise'];
	} 

	if(self && self.Promise) {
		lib.Promise = self.Promise;
		if(!lib.nativePromise) {
			lib.nativePromise = lib.Promise;
		}

		return;
	} else if(win && win.Promise) {
		lib.Promise = win.Promise;
		if(!lib.nativePromise) {
			lib.nativePromise = lib.Promise;
		}

		return;
	}
	
/**
 * bluebird build version 3.7.2
 * Features enabled: core
 * Features disabled: race, call_get, generators, map, nodeify, promisify, props, reduce, settle, some, using, timers, filter, any, each
*/
// jshint ignore: start
!function(t){if("object"==typeof exports&&"undefined"!=typeof module)module.exports=t();else if("function"==typeof define&&define.amd)define([],t);else{var e;"undefined"!=typeof window?e=window:"undefined"!=typeof global?e=global:"undefined"!=typeof self&&(e=self),e.Promise=t()}}(function(){var t,e,n;return function r(t,e,n){function o(a,s){if(!e[a]){if(!t[a]){var c="function"==typeof _dereq_&&_dereq_;if(!s&&c)return c(a,!0);if(i)return i(a,!0);var l=new Error("Cannot find module '"+a+"'");throw l.code="MODULE_NOT_FOUND",l}var u=e[a]={exports:{}};t[a][0].call(u.exports,function(e){var n=t[a][1][e];return o(n?n:e)},u,u.exports,r,t,e,n)}return e[a].exports}for(var i="function"==typeof _dereq_&&_dereq_,a=0;a<n.length;a++)o(n[a]);return o}({1:[function(t,e,n){"use strict";function r(){this._customScheduler=!1,this._isTickUsed=!1,this._lateQueue=new f(16),this._normalQueue=new f(16),this._haveDrainedQueues=!1;var t=this;this.drainQueues=function(){t._drainQueues()},this._schedule=p}function o(t,e,n){this._lateQueue.push(t,e,n),this._queueTick()}function i(t,e,n){this._normalQueue.push(t,e,n),this._queueTick()}function a(t){this._normalQueue._pushOne(t),this._queueTick()}function s(t){for(;t.length()>0;)c(t)}function c(t){var e=t.shift();if("function"!=typeof e)e._settlePromises();else{var n=t.shift(),r=t.shift();e.call(n,r)}}var l;try{throw new Error}catch(u){l=u}var p=t("./schedule"),f=t("./queue");r.prototype.setScheduler=function(t){var e=this._schedule;return this._schedule=t,this._customScheduler=!0,e},r.prototype.hasCustomScheduler=function(){return this._customScheduler},r.prototype.haveItemsQueued=function(){return this._isTickUsed||this._haveDrainedQueues},r.prototype.fatalError=function(t,e){e?(process.stderr.write("Fatal "+(t instanceof Error?t.stack:t)+"\n"),process.exit(2)):this.throwLater(t)},r.prototype.throwLater=function(t,e){if(1===arguments.length&&(e=t,t=function(){throw e}),"undefined"!=typeof setTimeout)setTimeout(function(){t(e)},0);else try{this._schedule(function(){t(e)})}catch(n){throw new Error("No async scheduler available\n\n    See http://goo.gl/MqrFmX\n")}},r.prototype.invokeLater=o,r.prototype.invoke=i,r.prototype.settlePromises=a,r.prototype._drainQueues=function(){s(this._normalQueue),this._reset(),this._haveDrainedQueues=!0,s(this._lateQueue)},r.prototype._queueTick=function(){this._isTickUsed||(this._isTickUsed=!0,this._schedule(this.drainQueues))},r.prototype._reset=function(){this._isTickUsed=!1},e.exports=r,e.exports.firstLineError=l},{"./queue":17,"./schedule":18}],2:[function(t,e,n){"use strict";e.exports=function(t,e,n,r){var o=!1,i=function(t,e){this._reject(e)},a=function(t,e){e.promiseRejectionQueued=!0,e.bindingPromise._then(i,i,null,this,t)},s=function(t,e){0===(50397184&this._bitField)&&this._resolveCallback(e.target)},c=function(t,e){e.promiseRejectionQueued||this._reject(t)};t.prototype.bind=function(i){o||(o=!0,t.prototype._propagateFrom=r.propagateFromFunction(),t.prototype._boundValue=r.boundValueFunction());var l=n(i),u=new t(e);u._propagateFrom(this,1);var p=this._target();if(u._setBoundTo(l),l instanceof t){var f={promiseRejectionQueued:!1,promise:u,target:p,bindingPromise:l};p._then(e,a,void 0,u,f),l._then(s,c,void 0,u,f),u._setOnCancel(l)}else u._resolveCallback(p);return u},t.prototype._setBoundTo=function(t){void 0!==t?(this._bitField=2097152|this._bitField,this._boundTo=t):this._bitField=-2097153&this._bitField},t.prototype._isBound=function(){return 2097152===(2097152&this._bitField)},t.bind=function(e,n){return t.resolve(n).bind(e)}}},{}],3:[function(t,e,n){"use strict";function r(){try{Promise===i&&(Promise=o)}catch(t){}return i}var o;"undefined"!=typeof Promise&&(o=Promise);var i=t("./promise")();i.noConflict=r,e.exports=i},{"./promise":15}],4:[function(t,e,n){"use strict";e.exports=function(e,n,r,o){var i=t("./util"),a=i.tryCatch,s=i.errorObj,c=e._async;e.prototype["break"]=e.prototype.cancel=function(){if(!o.cancellation())return this._warn("cancellation is disabled");for(var t=this,e=t;t._isCancellable();){if(!t._cancelBy(e)){e._isFollowing()?e._followee().cancel():e._cancelBranched();break}var n=t._cancellationParent;if(null==n||!n._isCancellable()){t._isFollowing()?t._followee().cancel():t._cancelBranched();break}t._isFollowing()&&t._followee().cancel(),t._setWillBeCancelled(),e=t,t=n}},e.prototype._branchHasCancelled=function(){this._branchesRemainingToCancel--},e.prototype._enoughBranchesHaveCancelled=function(){return void 0===this._branchesRemainingToCancel||this._branchesRemainingToCancel<=0},e.prototype._cancelBy=function(t){return t===this?(this._branchesRemainingToCancel=0,this._invokeOnCancel(),!0):(this._branchHasCancelled(),this._enoughBranchesHaveCancelled()?(this._invokeOnCancel(),!0):!1)},e.prototype._cancelBranched=function(){this._enoughBranchesHaveCancelled()&&this._cancel()},e.prototype._cancel=function(){this._isCancellable()&&(this._setCancelled(),c.invoke(this._cancelPromises,this,void 0))},e.prototype._cancelPromises=function(){this._length()>0&&this._settlePromises()},e.prototype._unsetOnCancel=function(){this._onCancelField=void 0},e.prototype._isCancellable=function(){return this.isPending()&&!this._isCancelled()},e.prototype.isCancellable=function(){return this.isPending()&&!this.isCancelled()},e.prototype._doInvokeOnCancel=function(t,e){if(i.isArray(t))for(var n=0;n<t.length;++n)this._doInvokeOnCancel(t[n],e);else if(void 0!==t)if("function"==typeof t){if(!e){var r=a(t).call(this._boundValue());r===s&&(this._attachExtraTrace(r.e),c.throwLater(r.e))}}else t._resultCancelled(this)},e.prototype._invokeOnCancel=function(){var t=this._onCancel();this._unsetOnCancel(),c.invoke(this._doInvokeOnCancel,this,t)},e.prototype._invokeInternalOnCancel=function(){this._isCancellable()&&(this._doInvokeOnCancel(this._onCancel(),!0),this._unsetOnCancel())},e.prototype._resultCancelled=function(){this.cancel()}}},{"./util":21}],5:[function(t,e,n){"use strict";e.exports=function(e){function n(t,n,s){return function(c){var l=s._boundValue();t:for(var u=0;u<t.length;++u){var p=t[u];if(p===Error||null!=p&&p.prototype instanceof Error){if(c instanceof p)return i(n).call(l,c)}else if("function"==typeof p){var f=i(p).call(l,c);if(f===a)return f;if(f)return i(n).call(l,c)}else if(r.isObject(c)){for(var h=o(p),d=0;d<h.length;++d){var _=h[d];if(p[_]!=c[_])continue t}return i(n).call(l,c)}}return e}}var r=t("./util"),o=t("./es5").keys,i=r.tryCatch,a=r.errorObj;return n}},{"./es5":10,"./util":21}],6:[function(t,e,n){"use strict";e.exports=function(t){function e(){this._trace=new e.CapturedTrace(r())}function n(){return o?new e:void 0}function r(){var t=i.length-1;return t>=0?i[t]:void 0}var o=!1,i=[];return t.prototype._promiseCreated=function(){},t.prototype._pushContext=function(){},t.prototype._popContext=function(){return null},t._peekContext=t.prototype._peekContext=function(){},e.prototype._pushContext=function(){void 0!==this._trace&&(this._trace._promiseCreated=null,i.push(this._trace))},e.prototype._popContext=function(){if(void 0!==this._trace){var t=i.pop(),e=t._promiseCreated;return t._promiseCreated=null,e}return null},e.CapturedTrace=null,e.create=n,e.deactivateLongStackTraces=function(){},e.activateLongStackTraces=function(){var n=t.prototype._pushContext,i=t.prototype._popContext,a=t._peekContext,s=t.prototype._peekContext,c=t.prototype._promiseCreated;e.deactivateLongStackTraces=function(){t.prototype._pushContext=n,t.prototype._popContext=i,t._peekContext=a,t.prototype._peekContext=s,t.prototype._promiseCreated=c,o=!1},o=!0,t.prototype._pushContext=e.prototype._pushContext,t.prototype._popContext=e.prototype._popContext,t._peekContext=t.prototype._peekContext=r,t.prototype._promiseCreated=function(){var t=this._peekContext();t&&null==t._promiseCreated&&(t._promiseCreated=this)}},e}},{}],7:[function(t,e,n){"use strict";e.exports=function(e,n,r,o){function i(t,e){return{promise:e}}function a(){return!1}function s(t,e,n){var r=this;try{t(e,n,function(t){if("function"!=typeof t)throw new TypeError("onCancel must be a function, got: "+V.toString(t));r._attachCancellationCallback(t)})}catch(o){return o}}function c(t){if(!this._isCancellable())return this;var e=this._onCancel();void 0!==e?V.isArray(e)?e.push(t):this._setOnCancel([e,t]):this._setOnCancel(t)}function l(){return this._onCancelField}function u(t){this._onCancelField=t}function p(){this._cancellationParent=void 0,this._onCancelField=void 0}function f(t,e){if(0!==(1&e)){this._cancellationParent=t;var n=t._branchesRemainingToCancel;void 0===n&&(n=0),t._branchesRemainingToCancel=n+1}0!==(2&e)&&t._isBound()&&this._setBoundTo(t._boundTo)}function h(t,e){0!==(2&e)&&t._isBound()&&this._setBoundTo(t._boundTo)}function d(){var t=this._boundTo;return void 0!==t&&t instanceof e?t.isFulfilled()?t.value():void 0:t}function _(){this._trace=new H(this._peekContext())}function v(t,e){if(q(t)){var n=this._trace;if(void 0!==n&&e&&(n=n._parent),void 0!==n)n.attachExtraTrace(t);else if(!t.__stackCleaned__){var r=F(t);V.notEnumerableProp(t,"stack",r.message+"\n"+r.stack.join("\n")),V.notEnumerableProp(t,"__stackCleaned__",!0)}}}function y(){this._trace=void 0}function g(t,e,n,r,o){if(void 0===t&&null!==e&&Z){if(void 0!==o&&o._returnedNonUndefined())return;if(0===(65535&r._bitField))return;n&&(n+=" ");var i="",a="";if(e._trace){for(var s=e._trace.stack.split("\n"),c=E(s),l=c.length-1;l>=0;--l){var u=c[l];if(!M.test(u)){var p=u.match(W);p&&(i="at "+p[1]+":"+p[2]+":"+p[3]+" ");break}}if(c.length>0)for(var f=c[0],l=0;l<s.length;++l)if(s[l]===f){l>0&&(a="\n"+s[l-1]);break}}var h="a promise was created in a "+n+"handler "+i+"but was not returned from it, see http://goo.gl/rRqMUw"+a;r._warn(h,!0,e)}}function m(t,e){var n=t+" is deprecated and will be removed in a future version.";return e&&(n+=" Use "+e+" instead."),b(n)}function b(t,n,r){if(ut.warnings){var o,i=new D(t);if(n)r._attachExtraTrace(i);else if(ut.longStackTraces&&(o=e._peekContext()))o.attachExtraTrace(i);else{var a=F(i);i.stack=a.message+"\n"+a.stack.join("\n")}it("warning",i)||T(i,"",!0)}}function C(t,e){for(var n=0;n<e.length-1;++n)e[n].push("From previous event:"),e[n]=e[n].join("\n");return n<e.length&&(e[n]=e[n].join("\n")),t+"\n"+e.join("\n")}function w(t){for(var e=0;e<t.length;++e)(0===t[e].length||e+1<t.length&&t[e][0]===t[e+1][0])&&(t.splice(e,1),e--)}function k(t){for(var e=t[0],n=1;n<t.length;++n){for(var r=t[n],o=e.length-1,i=e[o],a=-1,s=r.length-1;s>=0;--s)if(r[s]===i){a=s;break}for(var s=a;s>=0;--s){var c=r[s];if(e[o]!==c)break;e.pop(),o--}e=r}}function E(t){for(var e=[],n=0;n<t.length;++n){var r=t[n],o="    (No stack trace)"===r||$.test(r),i=o&&st(r);o&&!i&&(X&&" "!==r.charAt(0)&&(r="    "+r),e.push(r))}return e}function j(t){for(var e=t.stack.replace(/\s+$/g,"").split("\n"),n=0;n<e.length;++n){var r=e[n];if("    (No stack trace)"===r||$.test(r))break}return n>0&&"SyntaxError"!=t.name&&(e=e.slice(n)),e}function F(t){var e=t.stack,n=t.toString();return e="string"==typeof e&&e.length>0?j(t):["    (No stack trace)"],{message:n,stack:"SyntaxError"==t.name?e:E(e)}}function T(t,e,n){if("undefined"!=typeof console){var r;if(V.isObject(t)){var o=t.stack;r=e+z(o,t)}else r=e+String(t);"function"==typeof B?B(r,n):("function"==typeof console.log||"object"==typeof console.log)&&console.log(r)}}function x(t,e,n,r){var o=!1;try{"function"==typeof e&&(o=!0,"rejectionHandled"===t?e(r):e(n,r))}catch(i){I.throwLater(i)}"unhandledRejection"===t?it(t,n,r)||o||T(n,"Unhandled rejection "):it(t,r)}function R(t){var e;if("function"==typeof t)e="[function "+(t.name||"anonymous")+"]";else{e=t&&"function"==typeof t.toString?t.toString():V.toString(t);var n=/\[object [a-zA-Z0-9$_]+\]/;if(n.test(e))try{var r=JSON.stringify(t);e=r}catch(o){}0===e.length&&(e="(empty array)")}return"(<"+S(e)+">, no stack trace)"}function S(t){var e=41;return t.length<e?t:t.substr(0,e-3)+"..."}function P(){return"function"==typeof lt}function O(t){var e=t.match(ct);return e?{fileName:e[1],line:parseInt(e[2],10)}:void 0}function A(t,e){if(P()){for(var n,r,o=(t.stack||"").split("\n"),i=(e.stack||"").split("\n"),a=-1,s=-1,c=0;c<o.length;++c){var l=O(o[c]);if(l){n=l.fileName,a=l.line;break}}for(var c=0;c<i.length;++c){var l=O(i[c]);if(l){r=l.fileName,s=l.line;break}}0>a||0>s||!n||!r||n!==r||a>=s||(st=function(t){if(G.test(t))return!0;var e=O(t);return e&&e.fileName===n&&a<=e.line&&e.line<=s?!0:!1})}}function H(t){this._parent=t,this._promisesCreated=0;var e=this._length=1+(void 0===t?0:t._length);lt(this,H),e>32&&this.uncycle()}var N,L,B,U,I=e._async,D=t("./errors").Warning,V=t("./util"),Q=t("./es5"),q=V.canAttachTrace,G=/[\\\/]bluebird[\\\/]js[\\\/](release|debug|instrumented)/,M=/\((?:timers\.js):\d+:\d+\)/,W=/[\/<\(](.+?):(\d+):(\d+)\)?\s*$/,$=null,z=null,X=!1,K=!(0==V.env("BLUEBIRD_DEBUG")||!V.env("BLUEBIRD_DEBUG")&&"development"!==V.env("NODE_ENV")),J=!(0==V.env("BLUEBIRD_WARNINGS")||!K&&!V.env("BLUEBIRD_WARNINGS")),Y=!(0==V.env("BLUEBIRD_LONG_STACK_TRACES")||!K&&!V.env("BLUEBIRD_LONG_STACK_TRACES")),Z=0!=V.env("BLUEBIRD_W_FORGOTTEN_RETURN")&&(J||!!V.env("BLUEBIRD_W_FORGOTTEN_RETURN"));!function(){function t(){for(var t=0;t<r.length;++t)r[t]._notifyUnhandledRejection();n()}function n(){r.length=0}var r=[];U=function(e){r.push(e),setTimeout(t,1)},Q.defineProperty(e,"_unhandledRejectionCheck",{value:t}),Q.defineProperty(e,"_unhandledRejectionClear",{value:n})}(),e.prototype.suppressUnhandledRejections=function(){var t=this._target();t._bitField=-1048577&t._bitField|524288},e.prototype._ensurePossibleRejectionHandled=function(){0===(524288&this._bitField)&&(this._setRejectionIsUnhandled(),U(this))},e.prototype._notifyUnhandledRejectionIsHandled=function(){x("rejectionHandled",N,void 0,this)},e.prototype._setReturnedNonUndefined=function(){this._bitField=268435456|this._bitField},e.prototype._returnedNonUndefined=function(){return 0!==(268435456&this._bitField)},e.prototype._notifyUnhandledRejection=function(){if(this._isRejectionUnhandled()){var t=this._settledValue();this._setUnhandledRejectionIsNotified(),x("unhandledRejection",L,t,this)}},e.prototype._setUnhandledRejectionIsNotified=function(){this._bitField=262144|this._bitField},e.prototype._unsetUnhandledRejectionIsNotified=function(){this._bitField=-262145&this._bitField},e.prototype._isUnhandledRejectionNotified=function(){return(262144&this._bitField)>0},e.prototype._setRejectionIsUnhandled=function(){this._bitField=1048576|this._bitField},e.prototype._unsetRejectionIsUnhandled=function(){this._bitField=-1048577&this._bitField,this._isUnhandledRejectionNotified()&&(this._unsetUnhandledRejectionIsNotified(),this._notifyUnhandledRejectionIsHandled())},e.prototype._isRejectionUnhandled=function(){return(1048576&this._bitField)>0},e.prototype._warn=function(t,e,n){return b(t,e,n||this)},e.onPossiblyUnhandledRejection=function(t){var n=e._getContext();L=V.contextBind(n,t)},e.onUnhandledRejectionHandled=function(t){var n=e._getContext();N=V.contextBind(n,t)};var tt=function(){};e.longStackTraces=function(){if(I.haveItemsQueued()&&!ut.longStackTraces)throw new Error("cannot enable long stack traces after promises have been created\n\n    See http://goo.gl/MqrFmX\n");if(!ut.longStackTraces&&P()){var t=e.prototype._captureStackTrace,r=e.prototype._attachExtraTrace,o=e.prototype._dereferenceTrace;ut.longStackTraces=!0,tt=function(){if(I.haveItemsQueued()&&!ut.longStackTraces)throw new Error("cannot enable long stack traces after promises have been created\n\n    See http://goo.gl/MqrFmX\n");e.prototype._captureStackTrace=t,e.prototype._attachExtraTrace=r,e.prototype._dereferenceTrace=o,n.deactivateLongStackTraces(),ut.longStackTraces=!1},e.prototype._captureStackTrace=_,e.prototype._attachExtraTrace=v,e.prototype._dereferenceTrace=y,n.activateLongStackTraces()}},e.hasLongStackTraces=function(){return ut.longStackTraces&&P()};var et={unhandledrejection:{before:function(){var t=V.global.onunhandledrejection;return V.global.onunhandledrejection=null,t},after:function(t){V.global.onunhandledrejection=t}},rejectionhandled:{before:function(){var t=V.global.onrejectionhandled;return V.global.onrejectionhandled=null,t},after:function(t){V.global.onrejectionhandled=t}}},nt=function(){var t=function(t,e){if(!t)return!V.global.dispatchEvent(e);var n;try{return n=t.before(),!V.global.dispatchEvent(e)}finally{t.after(n)}};try{if("function"==typeof CustomEvent){var e=new CustomEvent("CustomEvent");return V.global.dispatchEvent(e),function(e,n){e=e.toLowerCase();var r={detail:n,cancelable:!0},o=new CustomEvent(e,r);return Q.defineProperty(o,"promise",{value:n.promise}),Q.defineProperty(o,"reason",{value:n.reason}),t(et[e],o)}}if("function"==typeof Event){var e=new Event("CustomEvent");return V.global.dispatchEvent(e),function(e,n){e=e.toLowerCase();var r=new Event(e,{cancelable:!0});return r.detail=n,Q.defineProperty(r,"promise",{value:n.promise}),Q.defineProperty(r,"reason",{value:n.reason}),t(et[e],r)}}var e=document.createEvent("CustomEvent");return e.initCustomEvent("testingtheevent",!1,!0,{}),V.global.dispatchEvent(e),function(e,n){e=e.toLowerCase();var r=document.createEvent("CustomEvent");return r.initCustomEvent(e,!1,!0,n),t(et[e],r)}}catch(n){}return function(){return!1}}(),rt=function(){return V.isNode?function(){return process.emit.apply(process,arguments)}:V.global?function(t){var e="on"+t.toLowerCase(),n=V.global[e];return n?(n.apply(V.global,[].slice.call(arguments,1)),!0):!1}:function(){return!1}}(),ot={promiseCreated:i,promiseFulfilled:i,promiseRejected:i,promiseResolved:i,promiseCancelled:i,promiseChained:function(t,e,n){return{promise:e,child:n}},warning:function(t,e){return{warning:e}},unhandledRejection:function(t,e,n){return{reason:e,promise:n}},rejectionHandled:i},it=function(t){var e=!1;try{e=rt.apply(null,arguments)}catch(n){I.throwLater(n),e=!0}var r=!1;try{r=nt(t,ot[t].apply(null,arguments))}catch(n){I.throwLater(n),r=!0}return r||e};e.config=function(t){if(t=Object(t),"longStackTraces"in t&&(t.longStackTraces?e.longStackTraces():!t.longStackTraces&&e.hasLongStackTraces()&&tt()),"warnings"in t){var n=t.warnings;ut.warnings=!!n,Z=ut.warnings,V.isObject(n)&&"wForgottenReturn"in n&&(Z=!!n.wForgottenReturn)}if("cancellation"in t&&t.cancellation&&!ut.cancellation){if(I.haveItemsQueued())throw new Error("cannot enable cancellation after promises are in use");e.prototype._clearCancellationData=p,e.prototype._propagateFrom=f,e.prototype._onCancel=l,e.prototype._setOnCancel=u,e.prototype._attachCancellationCallback=c,e.prototype._execute=s,at=f,ut.cancellation=!0}if("monitoring"in t&&(t.monitoring&&!ut.monitoring?(ut.monitoring=!0,e.prototype._fireEvent=it):!t.monitoring&&ut.monitoring&&(ut.monitoring=!1,e.prototype._fireEvent=a)),"asyncHooks"in t&&V.nodeSupportsAsyncResource){var i=ut.asyncHooks,h=!!t.asyncHooks;i!==h&&(ut.asyncHooks=h,h?r():o())}return e},e.prototype._fireEvent=a,e.prototype._execute=function(t,e,n){try{t(e,n)}catch(r){return r}},e.prototype._onCancel=function(){},e.prototype._setOnCancel=function(t){},e.prototype._attachCancellationCallback=function(t){},e.prototype._captureStackTrace=function(){},e.prototype._attachExtraTrace=function(){},e.prototype._dereferenceTrace=function(){},e.prototype._clearCancellationData=function(){},e.prototype._propagateFrom=function(t,e){};var at=h,st=function(){return!1},ct=/[\/<\(]([^:\/]+):(\d+):(?:\d+)\)?\s*$/;V.inherits(H,Error),n.CapturedTrace=H,H.prototype.uncycle=function(){var t=this._length;if(!(2>t)){for(var e=[],n={},r=0,o=this;void 0!==o;++r)e.push(o),o=o._parent;t=this._length=r;for(var r=t-1;r>=0;--r){var i=e[r].stack;void 0===n[i]&&(n[i]=r)}for(var r=0;t>r;++r){var a=e[r].stack,s=n[a];if(void 0!==s&&s!==r){s>0&&(e[s-1]._parent=void 0,e[s-1]._length=1),e[r]._parent=void 0,e[r]._length=1;var c=r>0?e[r-1]:this;t-1>s?(c._parent=e[s+1],c._parent.uncycle(),c._length=c._parent._length+1):(c._parent=void 0,c._length=1);for(var l=c._length+1,u=r-2;u>=0;--u)e[u]._length=l,l++;return}}}},H.prototype.attachExtraTrace=function(t){if(!t.__stackCleaned__){this.uncycle();for(var e=F(t),n=e.message,r=[e.stack],o=this;void 0!==o;)r.push(E(o.stack.split("\n"))),o=o._parent;k(r),w(r),V.notEnumerableProp(t,"stack",C(n,r)),V.notEnumerableProp(t,"__stackCleaned__",!0)}};var lt=function(){var t=/^\s*at\s*/,e=function(t,e){return"string"==typeof t?t:void 0!==e.name&&void 0!==e.message?e.toString():R(e)};if("number"==typeof Error.stackTraceLimit&&"function"==typeof Error.captureStackTrace){Error.stackTraceLimit+=6,$=t,z=e;var n=Error.captureStackTrace;return st=function(t){return G.test(t)},function(t,e){Error.stackTraceLimit+=6,n(t,e),Error.stackTraceLimit-=6}}var r=new Error;if("string"==typeof r.stack&&r.stack.split("\n")[0].indexOf("stackDetection@")>=0)return $=/@/,z=e,X=!0,function(t){t.stack=(new Error).stack};var o;try{throw new Error}catch(i){o="stack"in i}return"stack"in r||!o||"number"!=typeof Error.stackTraceLimit?(z=function(t,e){return"string"==typeof t?t:"object"!=typeof e&&"function"!=typeof e||void 0===e.name||void 0===e.message?R(e):e.toString()},null):($=t,z=e,function(t){Error.stackTraceLimit+=6;try{throw new Error}catch(e){t.stack=e.stack}Error.stackTraceLimit-=6})}([]);"undefined"!=typeof console&&"undefined"!=typeof console.warn&&(B=function(t){console.warn(t)},V.isNode&&process.stderr.isTTY?B=function(t,e){var n=e?"[33m":"[31m";console.warn(n+t+"[0m\n")}:V.isNode||"string"!=typeof(new Error).stack||(B=function(t,e){console.warn("%c"+t,e?"color: darkorange":"color: red")}));var ut={warnings:J,longStackTraces:!1,cancellation:!1,monitoring:!1,asyncHooks:!1};return Y&&e.longStackTraces(),{asyncHooks:function(){return ut.asyncHooks},longStackTraces:function(){return ut.longStackTraces},warnings:function(){return ut.warnings},cancellation:function(){return ut.cancellation},monitoring:function(){return ut.monitoring},propagateFromFunction:function(){return at},boundValueFunction:function(){return d},checkForgottenReturns:g,setBounds:A,warn:b,deprecated:m,CapturedTrace:H,fireDomEvent:nt,fireGlobalEvent:rt}}},{"./errors":9,"./es5":10,"./util":21}],8:[function(t,e,n){"use strict";e.exports=function(t){function e(){return this.value}function n(){throw this.reason}t.prototype["return"]=t.prototype.thenReturn=function(n){return n instanceof t&&n.suppressUnhandledRejections(),this._then(e,void 0,void 0,{value:n},void 0)},t.prototype["throw"]=t.prototype.thenThrow=function(t){return this._then(n,void 0,void 0,{reason:t},void 0)},t.prototype.catchThrow=function(t){if(arguments.length<=1)return this._then(void 0,n,void 0,{reason:t},void 0);var e=arguments[1],r=function(){throw e};return this.caught(t,r)},t.prototype.catchReturn=function(n){if(arguments.length<=1)return n instanceof t&&n.suppressUnhandledRejections(),this._then(void 0,e,void 0,{value:n},void 0);var r=arguments[1];r instanceof t&&r.suppressUnhandledRejections();var o=function(){return r};return this.caught(n,o)}}},{}],9:[function(t,e,n){"use strict";function r(t,e){function n(r){return this instanceof n?(p(this,"message","string"==typeof r?r:e),p(this,"name",t),void(Error.captureStackTrace?Error.captureStackTrace(this,this.constructor):Error.call(this))):new n(r)}return u(n,Error),n}function o(t){return this instanceof o?(p(this,"name","OperationalError"),p(this,"message",t),this.cause=t,this.isOperational=!0,void(t instanceof Error?(p(this,"message",t.message),p(this,"stack",t.stack)):Error.captureStackTrace&&Error.captureStackTrace(this,this.constructor))):new o(t)}var i,a,s=t("./es5"),c=s.freeze,l=t("./util"),u=l.inherits,p=l.notEnumerableProp,f=r("Warning","warning"),h=r("CancellationError","cancellation error"),d=r("TimeoutError","timeout error"),_=r("AggregateError","aggregate error");try{i=TypeError,a=RangeError}catch(v){i=r("TypeError","type error"),a=r("RangeError","range error")}for(var y="join pop push shift unshift slice filter forEach some every map indexOf lastIndexOf reduce reduceRight sort reverse".split(" "),g=0;g<y.length;++g)"function"==typeof Array.prototype[y[g]]&&(_.prototype[y[g]]=Array.prototype[y[g]]);s.defineProperty(_.prototype,"length",{value:0,configurable:!1,writable:!0,enumerable:!0}),_.prototype.isOperational=!0;var m=0;_.prototype.toString=function(){var t=Array(4*m+1).join(" "),e="\n"+t+"AggregateError of:\n";m++,t=Array(4*m+1).join(" ");for(var n=0;n<this.length;++n){for(var r=this[n]===this?"[Circular AggregateError]":this[n]+"",o=r.split("\n"),i=0;i<o.length;++i)o[i]=t+o[i];r=o.join("\n"),e+=r+"\n"}return m--,e},u(o,Error);var b=Error.__BluebirdErrorTypes__;b||(b=c({CancellationError:h,TimeoutError:d,OperationalError:o,RejectionError:o,AggregateError:_}),s.defineProperty(Error,"__BluebirdErrorTypes__",{value:b,writable:!1,enumerable:!1,configurable:!1})),e.exports={Error:Error,TypeError:i,RangeError:a,CancellationError:b.CancellationError,OperationalError:b.OperationalError,TimeoutError:b.TimeoutError,AggregateError:b.AggregateError,Warning:f}},{"./es5":10,"./util":21}],10:[function(t,e,n){var r=function(){"use strict";return void 0===this}();if(r)e.exports={freeze:Object.freeze,defineProperty:Object.defineProperty,getDescriptor:Object.getOwnPropertyDescriptor,keys:Object.keys,names:Object.getOwnPropertyNames,getPrototypeOf:Object.getPrototypeOf,isArray:Array.isArray,isES5:r,propertyIsWritable:function(t,e){var n=Object.getOwnPropertyDescriptor(t,e);return!(n&&!n.writable&&!n.set)}};else{var o={}.hasOwnProperty,i={}.toString,a={}.constructor.prototype,s=function(t){var e=[];for(var n in t)o.call(t,n)&&e.push(n);return e},c=function(t,e){return{value:t[e]}},l=function(t,e,n){return t[e]=n.value,t},u=function(t){return t},p=function(t){try{return Object(t).constructor.prototype}catch(e){return a}},f=function(t){try{return"[object Array]"===i.call(t)}catch(e){return!1}};e.exports={isArray:f,keys:s,names:s,defineProperty:l,getDescriptor:c,freeze:u,getPrototypeOf:p,isES5:r,propertyIsWritable:function(){return!0}}}},{}],11:[function(t,e,n){"use strict";e.exports=function(e,n,r){function o(t,e,n){this.promise=t,this.type=e,this.handler=n,this.called=!1,this.cancelPromise=null}function i(t){this.finallyHandler=t}function a(t,e){return null!=t.cancelPromise?(arguments.length>1?t.cancelPromise._reject(e):t.cancelPromise._cancel(),t.cancelPromise=null,!0):!1}function s(){return l.call(this,this.promise._target()._settledValue())}function c(t){return a(this,t)?void 0:(f.e=t,f)}function l(t){var o=this.promise,l=this.handler;if(!this.called){this.called=!0;var u=this.isFinallyHandler()?l.call(o._boundValue()):l.call(o._boundValue(),t);if(u===r)return u;if(void 0!==u){o._setReturnedNonUndefined();var h=n(u,o);if(h instanceof e){if(null!=this.cancelPromise){if(h._isCancelled()){var d=new p("late cancellation observer");return o._attachExtraTrace(d),f.e=d,f}h.isPending()&&h._attachCancellationCallback(new i(this))}return h._then(s,c,void 0,this,void 0)}}}return o.isRejected()?(a(this),f.e=t,f):(a(this),t)}var u=t("./util"),p=e.CancellationError,f=u.errorObj,h=t("./catch_filter")(r);return o.prototype.isFinallyHandler=function(){return 0===this.type},i.prototype._resultCancelled=function(){a(this.finallyHandler)},e.prototype._passThrough=function(t,e,n,r){return"function"!=typeof t?this.then():this._then(n,r,void 0,new o(this,e,t),void 0)},e.prototype.lastly=e.prototype["finally"]=function(t){return this._passThrough(t,0,l,l)},e.prototype.tap=function(t){return this._passThrough(t,1,l)},e.prototype.tapCatch=function(t){var n=arguments.length;if(1===n)return this._passThrough(t,1,void 0,l);var r,o=new Array(n-1),i=0;for(r=0;n-1>r;++r){var a=arguments[r];if(!u.isObject(a))return e.reject(new TypeError("tapCatch statement predicate: expecting an object but got "+u.classString(a)));o[i++]=a}o.length=i;var s=arguments[r];return this._passThrough(h(o,s,this),1,void 0,l)},o}},{"./catch_filter":5,"./util":21}],12:[function(t,e,n){"use strict";e.exports=function(e,n,r,o,i){var a=t("./util");a.canEvaluate,a.tryCatch,a.errorObj;e.join=function(){var t,e=arguments.length-1;if(e>0&&"function"==typeof arguments[e]){t=arguments[e];var r}var o=[].slice.call(arguments);t&&o.pop();var r=new n(o).promise();return void 0!==t?r.spread(t):r}}},{"./util":21}],13:[function(t,e,n){"use strict";e.exports=function(e,n,r,o,i){var a=t("./util"),s=a.tryCatch;e.method=function(t){if("function"!=typeof t)throw new e.TypeError("expecting a function but got "+a.classString(t));return function(){var r=new e(n);r._captureStackTrace(),r._pushContext();var o=s(t).apply(this,arguments),a=r._popContext();return i.checkForgottenReturns(o,a,"Promise.method",r),r._resolveFromSyncValue(o),r}},e.attempt=e["try"]=function(t){if("function"!=typeof t)return o("expecting a function but got "+a.classString(t));var r=new e(n);r._captureStackTrace(),r._pushContext();var c;if(arguments.length>1){i.deprecated("calling Promise.try with more than 1 argument");var l=arguments[1],u=arguments[2];c=a.isArray(l)?s(t).apply(u,l):s(t).call(u,l)}else c=s(t)();var p=r._popContext();return i.checkForgottenReturns(c,p,"Promise.try",r),r._resolveFromSyncValue(c),r},e.prototype._resolveFromSyncValue=function(t){t===a.errorObj?this._rejectCallback(t.e,!1):this._resolveCallback(t,!0)}}},{"./util":21}],14:[function(t,e,n){"use strict";function r(t){return t instanceof Error&&u.getPrototypeOf(t)===Error.prototype}function o(t){var e;if(r(t)){e=new l(t),e.name=t.name,e.message=t.message,e.stack=t.stack;for(var n=u.keys(t),o=0;o<n.length;++o){var i=n[o];p.test(i)||(e[i]=t[i])}return e}return a.markAsOriginatingFromRejection(t),t}function i(t,e){return function(n,r){if(null!==t){if(n){var i=o(s(n));t._attachExtraTrace(i),t._reject(i)}else if(e){var a=[].slice.call(arguments,1);t._fulfill(a)}else t._fulfill(r);t=null}}}var a=t("./util"),s=a.maybeWrapAsError,c=t("./errors"),l=c.OperationalError,u=t("./es5"),p=/^(?:name|message|stack|cause)$/;e.exports=i},{"./errors":9,"./es5":10,"./util":21}],15:[function(t,e,n){"use strict";e.exports=function(){function n(){}function r(t,e){if(null==t||t.constructor!==o)throw new j("the promise constructor cannot be invoked directly\n\n    See http://goo.gl/MqrFmX\n");if("function"!=typeof e)throw new j("expecting a function but got "+f.classString(e))}function o(t){t!==T&&r(this,t),this._bitField=0,this._fulfillmentHandler0=void 0,this._rejectionHandler0=void 0,this._promise0=void 0,this._receiver0=void 0,this._resolveFromExecutor(t),this._promiseCreated(),this._fireEvent("promiseCreated",this)}function i(t){this.promise._resolveCallback(t)}function a(t){this.promise._rejectCallback(t,!1)}function s(t){var e=new o(T);e._fulfillmentHandler0=t,e._rejectionHandler0=t,e._promise0=t,e._receiver0=t}var c=function(){return new j("circular promise resolution chain\n\n    See http://goo.gl/MqrFmX\n")},l=function(){return new o.PromiseInspection(this._target())},u=function(t){return o.reject(new j(t))},p={},f=t("./util");f.setReflectHandler(l);var h=function(){var t=process.domain;return void 0===t?null:t},d=function(){return null},_=function(){return{domain:h(),async:null}},v=f.isNode&&f.nodeSupportsAsyncResource?t("async_hooks").AsyncResource:null,y=function(){return{domain:h(),async:new v("Bluebird::Promise")}},g=f.isNode?_:d;f.notEnumerableProp(o,"_getContext",g);var m=function(){g=y,f.notEnumerableProp(o,"_getContext",y)},b=function(){g=_,f.notEnumerableProp(o,"_getContext",_)},C=t("./es5"),w=t("./async"),k=new w;C.defineProperty(o,"_async",{value:k});var E=t("./errors"),j=o.TypeError=E.TypeError;o.RangeError=E.RangeError;var F=o.CancellationError=E.CancellationError;o.TimeoutError=E.TimeoutError,o.OperationalError=E.OperationalError,o.RejectionError=E.OperationalError,o.AggregateError=E.AggregateError;var T=function(){},x={},R={},S=t("./thenables")(o,T),P=t("./promise_array")(o,T,S,u,n),O=t("./context")(o),A=(O.create,t("./debuggability")(o,O,m,b)),H=(A.CapturedTrace,t("./finally")(o,S,R)),N=t("./catch_filter")(R),L=t("./nodeback"),B=f.errorObj,U=f.tryCatch;return o.prototype.toString=function(){return"[object Promise]"},o.prototype.caught=o.prototype["catch"]=function(t){var e=arguments.length;if(e>1){var n,r=new Array(e-1),o=0;
for(n=0;e-1>n;++n){var i=arguments[n];if(!f.isObject(i))return u("Catch statement predicate: expecting an object but got "+f.classString(i));r[o++]=i}if(r.length=o,t=arguments[n],"function"!=typeof t)throw new j("The last argument to .catch() must be a function, got "+f.toString(t));return this.then(void 0,N(r,t,this))}return this.then(void 0,t)},o.prototype.reflect=function(){return this._then(l,l,void 0,this,void 0)},o.prototype.then=function(t,e){if(A.warnings()&&arguments.length>0&&"function"!=typeof t&&"function"!=typeof e){var n=".then() only accepts functions but was passed: "+f.classString(t);arguments.length>1&&(n+=", "+f.classString(e)),this._warn(n)}return this._then(t,e,void 0,void 0,void 0)},o.prototype.done=function(t,e){var n=this._then(t,e,void 0,void 0,void 0);n._setIsFinal()},o.prototype.spread=function(t){return"function"!=typeof t?u("expecting a function but got "+f.classString(t)):this.all()._then(t,void 0,void 0,x,void 0)},o.prototype.toJSON=function(){var t={isFulfilled:!1,isRejected:!1,fulfillmentValue:void 0,rejectionReason:void 0};return this.isFulfilled()?(t.fulfillmentValue=this.value(),t.isFulfilled=!0):this.isRejected()&&(t.rejectionReason=this.reason(),t.isRejected=!0),t},o.prototype.all=function(){return arguments.length>0&&this._warn(".all() was passed arguments but it does not take any"),new P(this).promise()},o.prototype.error=function(t){return this.caught(f.originatesFromRejection,t)},o.getNewLibraryCopy=e.exports,o.is=function(t){return t instanceof o},o.fromNode=o.fromCallback=function(t){var e=new o(T);e._captureStackTrace();var n=arguments.length>1?!!Object(arguments[1]).multiArgs:!1,r=U(t)(L(e,n));return r===B&&e._rejectCallback(r.e,!0),e._isFateSealed()||e._setAsyncGuaranteed(),e},o.all=function(t){return new P(t).promise()},o.cast=function(t){var e=S(t);return e instanceof o||(e=new o(T),e._captureStackTrace(),e._setFulfilled(),e._rejectionHandler0=t),e},o.resolve=o.fulfilled=o.cast,o.reject=o.rejected=function(t){var e=new o(T);return e._captureStackTrace(),e._rejectCallback(t,!0),e},o.setScheduler=function(t){if("function"!=typeof t)throw new j("expecting a function but got "+f.classString(t));return k.setScheduler(t)},o.prototype._then=function(t,e,n,r,i){var a=void 0!==i,s=a?i:new o(T),c=this._target(),l=c._bitField;a||(s._propagateFrom(this,3),s._captureStackTrace(),void 0===r&&0!==(2097152&this._bitField)&&(r=0!==(50397184&l)?this._boundValue():c===this?void 0:this._boundTo),this._fireEvent("promiseChained",this,s));var u=g();if(0!==(50397184&l)){var p,h,d=c._settlePromiseCtx;0!==(33554432&l)?(h=c._rejectionHandler0,p=t):0!==(16777216&l)?(h=c._fulfillmentHandler0,p=e,c._unsetRejectionIsUnhandled()):(d=c._settlePromiseLateCancellationObserver,h=new F("late cancellation observer"),c._attachExtraTrace(h),p=e),k.invoke(d,c,{handler:f.contextBind(u,p),promise:s,receiver:r,value:h})}else c._addCallbacks(t,e,s,r,u);return s},o.prototype._length=function(){return 65535&this._bitField},o.prototype._isFateSealed=function(){return 0!==(117506048&this._bitField)},o.prototype._isFollowing=function(){return 67108864===(67108864&this._bitField)},o.prototype._setLength=function(t){this._bitField=-65536&this._bitField|65535&t},o.prototype._setFulfilled=function(){this._bitField=33554432|this._bitField,this._fireEvent("promiseFulfilled",this)},o.prototype._setRejected=function(){this._bitField=16777216|this._bitField,this._fireEvent("promiseRejected",this)},o.prototype._setFollowing=function(){this._bitField=67108864|this._bitField,this._fireEvent("promiseResolved",this)},o.prototype._setIsFinal=function(){this._bitField=4194304|this._bitField},o.prototype._isFinal=function(){return(4194304&this._bitField)>0},o.prototype._unsetCancelled=function(){this._bitField=-65537&this._bitField},o.prototype._setCancelled=function(){this._bitField=65536|this._bitField,this._fireEvent("promiseCancelled",this)},o.prototype._setWillBeCancelled=function(){this._bitField=8388608|this._bitField},o.prototype._setAsyncGuaranteed=function(){if(!k.hasCustomScheduler()){var t=this._bitField;this._bitField=t|(536870912&t)>>2^134217728}},o.prototype._setNoAsyncGuarantee=function(){this._bitField=-134217729&(536870912|this._bitField)},o.prototype._receiverAt=function(t){var e=0===t?this._receiver0:this[4*t-4+3];return e===p?void 0:void 0===e&&this._isBound()?this._boundValue():e},o.prototype._promiseAt=function(t){return this[4*t-4+2]},o.prototype._fulfillmentHandlerAt=function(t){return this[4*t-4+0]},o.prototype._rejectionHandlerAt=function(t){return this[4*t-4+1]},o.prototype._boundValue=function(){},o.prototype._migrateCallback0=function(t){var e=(t._bitField,t._fulfillmentHandler0),n=t._rejectionHandler0,r=t._promise0,o=t._receiverAt(0);void 0===o&&(o=p),this._addCallbacks(e,n,r,o,null)},o.prototype._migrateCallbackAt=function(t,e){var n=t._fulfillmentHandlerAt(e),r=t._rejectionHandlerAt(e),o=t._promiseAt(e),i=t._receiverAt(e);void 0===i&&(i=p),this._addCallbacks(n,r,o,i,null)},o.prototype._addCallbacks=function(t,e,n,r,o){var i=this._length();if(i>=65531&&(i=0,this._setLength(0)),0===i)this._promise0=n,this._receiver0=r,"function"==typeof t&&(this._fulfillmentHandler0=f.contextBind(o,t)),"function"==typeof e&&(this._rejectionHandler0=f.contextBind(o,e));else{var a=4*i-4;this[a+2]=n,this[a+3]=r,"function"==typeof t&&(this[a+0]=f.contextBind(o,t)),"function"==typeof e&&(this[a+1]=f.contextBind(o,e))}return this._setLength(i+1),i},o.prototype._proxy=function(t,e){this._addCallbacks(void 0,void 0,e,t,null)},o.prototype._resolveCallback=function(t,e){if(0===(117506048&this._bitField)){if(t===this)return this._rejectCallback(c(),!1);var n=S(t,this);if(!(n instanceof o))return this._fulfill(t);e&&this._propagateFrom(n,2);var r=n._target();if(r===this)return void this._reject(c());var i=r._bitField;if(0===(50397184&i)){var a=this._length();a>0&&r._migrateCallback0(this);for(var s=1;a>s;++s)r._migrateCallbackAt(this,s);this._setFollowing(),this._setLength(0),this._setFollowee(n)}else if(0!==(33554432&i))this._fulfill(r._value());else if(0!==(16777216&i))this._reject(r._reason());else{var l=new F("late cancellation observer");r._attachExtraTrace(l),this._reject(l)}}},o.prototype._rejectCallback=function(t,e,n){var r=f.ensureErrorObject(t),o=r===t;if(!o&&!n&&A.warnings()){var i="a promise was rejected with a non-error: "+f.classString(t);this._warn(i,!0)}this._attachExtraTrace(r,e?o:!1),this._reject(t)},o.prototype._resolveFromExecutor=function(t){if(t!==T){var e=this;this._captureStackTrace(),this._pushContext();var n=!0,r=this._execute(t,function(t){e._resolveCallback(t)},function(t){e._rejectCallback(t,n)});n=!1,this._popContext(),void 0!==r&&e._rejectCallback(r,!0)}},o.prototype._settlePromiseFromHandler=function(t,e,n,r){var o=r._bitField;if(0===(65536&o)){r._pushContext();var i;e===x?n&&"number"==typeof n.length?i=U(t).apply(this._boundValue(),n):(i=B,i.e=new j("cannot .spread() a non-array: "+f.classString(n))):i=U(t).call(e,n);var a=r._popContext();o=r._bitField,0===(65536&o)&&(i===R?r._reject(n):i===B?r._rejectCallback(i.e,!1):(A.checkForgottenReturns(i,a,"",r,this),r._resolveCallback(i)))}},o.prototype._target=function(){for(var t=this;t._isFollowing();)t=t._followee();return t},o.prototype._followee=function(){return this._rejectionHandler0},o.prototype._setFollowee=function(t){this._rejectionHandler0=t},o.prototype._settlePromise=function(t,e,r,i){var a=t instanceof o,s=this._bitField,c=0!==(134217728&s);0!==(65536&s)?(a&&t._invokeInternalOnCancel(),r instanceof H&&r.isFinallyHandler()?(r.cancelPromise=t,U(e).call(r,i)===B&&t._reject(B.e)):e===l?t._fulfill(l.call(r)):r instanceof n?r._promiseCancelled(t):a||t instanceof P?t._cancel():r.cancel()):"function"==typeof e?a?(c&&t._setAsyncGuaranteed(),this._settlePromiseFromHandler(e,r,i,t)):e.call(r,i,t):r instanceof n?r._isResolved()||(0!==(33554432&s)?r._promiseFulfilled(i,t):r._promiseRejected(i,t)):a&&(c&&t._setAsyncGuaranteed(),0!==(33554432&s)?t._fulfill(i):t._reject(i))},o.prototype._settlePromiseLateCancellationObserver=function(t){var e=t.handler,n=t.promise,r=t.receiver,i=t.value;"function"==typeof e?n instanceof o?this._settlePromiseFromHandler(e,r,i,n):e.call(r,i,n):n instanceof o&&n._reject(i)},o.prototype._settlePromiseCtx=function(t){this._settlePromise(t.promise,t.handler,t.receiver,t.value)},o.prototype._settlePromise0=function(t,e,n){var r=this._promise0,o=this._receiverAt(0);this._promise0=void 0,this._receiver0=void 0,this._settlePromise(r,t,o,e)},o.prototype._clearCallbackDataAtIndex=function(t){var e=4*t-4;this[e+2]=this[e+3]=this[e+0]=this[e+1]=void 0},o.prototype._fulfill=function(t){var e=this._bitField;if(!((117506048&e)>>>16)){if(t===this){var n=c();return this._attachExtraTrace(n),this._reject(n)}this._setFulfilled(),this._rejectionHandler0=t,(65535&e)>0&&(0!==(134217728&e)?this._settlePromises():k.settlePromises(this),this._dereferenceTrace())}},o.prototype._reject=function(t){var e=this._bitField;if(!((117506048&e)>>>16))return this._setRejected(),this._fulfillmentHandler0=t,this._isFinal()?k.fatalError(t,f.isNode):void((65535&e)>0?k.settlePromises(this):this._ensurePossibleRejectionHandled())},o.prototype._fulfillPromises=function(t,e){for(var n=1;t>n;n++){var r=this._fulfillmentHandlerAt(n),o=this._promiseAt(n),i=this._receiverAt(n);this._clearCallbackDataAtIndex(n),this._settlePromise(o,r,i,e)}},o.prototype._rejectPromises=function(t,e){for(var n=1;t>n;n++){var r=this._rejectionHandlerAt(n),o=this._promiseAt(n),i=this._receiverAt(n);this._clearCallbackDataAtIndex(n),this._settlePromise(o,r,i,e)}},o.prototype._settlePromises=function(){var t=this._bitField,e=65535&t;if(e>0){if(0!==(16842752&t)){var n=this._fulfillmentHandler0;this._settlePromise0(this._rejectionHandler0,n,t),this._rejectPromises(e,n)}else{var r=this._rejectionHandler0;this._settlePromise0(this._fulfillmentHandler0,r,t),this._fulfillPromises(e,r)}this._setLength(0)}this._clearCancellationData()},o.prototype._settledValue=function(){var t=this._bitField;return 0!==(33554432&t)?this._rejectionHandler0:0!==(16777216&t)?this._fulfillmentHandler0:void 0},"undefined"!=typeof Symbol&&Symbol.toStringTag&&C.defineProperty(o.prototype,Symbol.toStringTag,{get:function(){return"Object"}}),o.defer=o.pending=function(){A.deprecated("Promise.defer","new Promise");var t=new o(T);return{promise:t,resolve:i,reject:a}},f.notEnumerableProp(o,"_makeSelfResolutionError",c),t("./method")(o,T,S,u,A),t("./bind")(o,T,S,A),t("./cancel")(o,P,u,A),t("./direct_resolve")(o),t("./synchronous_inspection")(o),t("./join")(o,P,S,T,k),o.Promise=o,o.version="3.7.2",f.toFastProperties(o),f.toFastProperties(o.prototype),s({a:1}),s({b:2}),s({c:3}),s(1),s(function(){}),s(void 0),s(!1),s(new o(T)),A.setBounds(w.firstLineError,f.lastLineError),o}},{"./async":1,"./bind":2,"./cancel":4,"./catch_filter":5,"./context":6,"./debuggability":7,"./direct_resolve":8,"./errors":9,"./es5":10,"./finally":11,"./join":12,"./method":13,"./nodeback":14,"./promise_array":16,"./synchronous_inspection":19,"./thenables":20,"./util":21,async_hooks:void 0}],16:[function(t,e,n){"use strict";e.exports=function(e,n,r,o,i){function a(t){switch(t){case-2:return[];case-3:return{};case-6:return new Map}}function s(t){var r=this._promise=new e(n);t instanceof e&&(r._propagateFrom(t,3),t.suppressUnhandledRejections()),r._setOnCancel(this),this._values=t,this._length=0,this._totalResolved=0,this._init(void 0,-2)}var c=t("./util");c.isArray;return c.inherits(s,i),s.prototype.length=function(){return this._length},s.prototype.promise=function(){return this._promise},s.prototype._init=function l(t,n){var i=r(this._values,this._promise);if(i instanceof e){i=i._target();var s=i._bitField;if(this._values=i,0===(50397184&s))return this._promise._setAsyncGuaranteed(),i._then(l,this._reject,void 0,this,n);if(0===(33554432&s))return 0!==(16777216&s)?this._reject(i._reason()):this._cancel();i=i._value()}if(i=c.asArray(i),null===i){var u=o("expecting an array or an iterable object but got "+c.classString(i)).reason();return void this._promise._rejectCallback(u,!1)}return 0===i.length?void(-5===n?this._resolveEmptyArray():this._resolve(a(n))):void this._iterate(i)},s.prototype._iterate=function(t){var n=this.getActualLength(t.length);this._length=n,this._values=this.shouldCopyValues()?new Array(n):this._values;for(var o=this._promise,i=!1,a=null,s=0;n>s;++s){var c=r(t[s],o);c instanceof e?(c=c._target(),a=c._bitField):a=null,i?null!==a&&c.suppressUnhandledRejections():null!==a?0===(50397184&a)?(c._proxy(this,s),this._values[s]=c):i=0!==(33554432&a)?this._promiseFulfilled(c._value(),s):0!==(16777216&a)?this._promiseRejected(c._reason(),s):this._promiseCancelled(s):i=this._promiseFulfilled(c,s)}i||o._setAsyncGuaranteed()},s.prototype._isResolved=function(){return null===this._values},s.prototype._resolve=function(t){this._values=null,this._promise._fulfill(t)},s.prototype._cancel=function(){!this._isResolved()&&this._promise._isCancellable()&&(this._values=null,this._promise._cancel())},s.prototype._reject=function(t){this._values=null,this._promise._rejectCallback(t,!1)},s.prototype._promiseFulfilled=function(t,e){this._values[e]=t;var n=++this._totalResolved;return n>=this._length?(this._resolve(this._values),!0):!1},s.prototype._promiseCancelled=function(){return this._cancel(),!0},s.prototype._promiseRejected=function(t){return this._totalResolved++,this._reject(t),!0},s.prototype._resultCancelled=function(){if(!this._isResolved()){var t=this._values;if(this._cancel(),t instanceof e)t.cancel();else for(var n=0;n<t.length;++n)t[n]instanceof e&&t[n].cancel()}},s.prototype.shouldCopyValues=function(){return!0},s.prototype.getActualLength=function(t){return t},s}},{"./util":21}],17:[function(t,e,n){"use strict";function r(t,e,n,r,o){for(var i=0;o>i;++i)n[i+r]=t[i+e],t[i+e]=void 0}function o(t){this._capacity=t,this._length=0,this._front=0}o.prototype._willBeOverCapacity=function(t){return this._capacity<t},o.prototype._pushOne=function(t){var e=this.length();this._checkCapacity(e+1);var n=this._front+e&this._capacity-1;this[n]=t,this._length=e+1},o.prototype.push=function(t,e,n){var r=this.length()+3;if(this._willBeOverCapacity(r))return this._pushOne(t),this._pushOne(e),void this._pushOne(n);var o=this._front+r-3;this._checkCapacity(r);var i=this._capacity-1;this[o+0&i]=t,this[o+1&i]=e,this[o+2&i]=n,this._length=r},o.prototype.shift=function(){var t=this._front,e=this[t];return this[t]=void 0,this._front=t+1&this._capacity-1,this._length--,e},o.prototype.length=function(){return this._length},o.prototype._checkCapacity=function(t){this._capacity<t&&this._resizeTo(this._capacity<<1)},o.prototype._resizeTo=function(t){var e=this._capacity;this._capacity=t;var n=this._front,o=this._length,i=n+o&e-1;r(this,0,this,e,i)},e.exports=o},{}],18:[function(t,e,n){"use strict";var r,o=t("./util"),i=function(){throw new Error("No async scheduler available\n\n    See http://goo.gl/MqrFmX\n")},a=o.getNativePromise();if(o.isNode&&"undefined"==typeof MutationObserver){var s=global.setImmediate,c=process.nextTick;r=o.isRecentNode?function(t){s.call(global,t)}:function(t){c.call(process,t)}}else if("function"==typeof a&&"function"==typeof a.resolve){var l=a.resolve();r=function(t){l.then(t)}}else r="undefined"!=typeof MutationObserver&&("undefined"==typeof window||!window.navigator||!window.navigator.standalone&&!window.cordova)&&"classList"in document.documentElement?function(){var t=document.createElement("div"),e={attributes:!0},n=!1,r=document.createElement("div"),o=new MutationObserver(function(){t.classList.toggle("foo"),n=!1});o.observe(r,e);var i=function(){n||(n=!0,r.classList.toggle("foo"))};return function(n){var r=new MutationObserver(function(){r.disconnect(),n()});r.observe(t,e),i()}}():"undefined"!=typeof setImmediate?function(t){setImmediate(t)}:"undefined"!=typeof setTimeout?function(t){setTimeout(t,0)}:i;e.exports=r},{"./util":21}],19:[function(t,e,n){"use strict";e.exports=function(t){function e(t){void 0!==t?(t=t._target(),this._bitField=t._bitField,this._settledValueField=t._isFateSealed()?t._settledValue():void 0):(this._bitField=0,this._settledValueField=void 0)}e.prototype._settledValue=function(){return this._settledValueField};var n=e.prototype.value=function(){if(!this.isFulfilled())throw new TypeError("cannot get fulfillment value of a non-fulfilled promise\n\n    See http://goo.gl/MqrFmX\n");return this._settledValue()},r=e.prototype.error=e.prototype.reason=function(){if(!this.isRejected())throw new TypeError("cannot get rejection reason of a non-rejected promise\n\n    See http://goo.gl/MqrFmX\n");return this._settledValue()},o=e.prototype.isFulfilled=function(){return 0!==(33554432&this._bitField)},i=e.prototype.isRejected=function(){return 0!==(16777216&this._bitField)},a=e.prototype.isPending=function(){return 0===(50397184&this._bitField)},s=e.prototype.isResolved=function(){return 0!==(50331648&this._bitField)};e.prototype.isCancelled=function(){return 0!==(8454144&this._bitField)},t.prototype.__isCancelled=function(){return 65536===(65536&this._bitField)},t.prototype._isCancelled=function(){return this._target().__isCancelled()},t.prototype.isCancelled=function(){return 0!==(8454144&this._target()._bitField)},t.prototype.isPending=function(){return a.call(this._target())},t.prototype.isRejected=function(){return i.call(this._target())},t.prototype.isFulfilled=function(){return o.call(this._target())},t.prototype.isResolved=function(){return s.call(this._target())},t.prototype.value=function(){return n.call(this._target())},t.prototype.reason=function(){var t=this._target();return t._unsetRejectionIsUnhandled(),r.call(t)},t.prototype._value=function(){return this._settledValue()},t.prototype._reason=function(){return this._unsetRejectionIsUnhandled(),this._settledValue()},t.PromiseInspection=e}},{}],20:[function(t,e,n){"use strict";e.exports=function(e,n){function r(t,r){if(u(t)){if(t instanceof e)return t;var o=i(t);if(o===l){r&&r._pushContext();var c=e.reject(o.e);return r&&r._popContext(),c}if("function"==typeof o){if(a(t)){var c=new e(n);return t._then(c._fulfill,c._reject,void 0,c,null),c}return s(t,o,r)}}return t}function o(t){return t.then}function i(t){try{return o(t)}catch(e){return l.e=e,l}}function a(t){try{return p.call(t,"_promise0")}catch(e){return!1}}function s(t,r,o){function i(t){s&&(s._resolveCallback(t),s=null)}function a(t){s&&(s._rejectCallback(t,p,!0),s=null)}var s=new e(n),u=s;o&&o._pushContext(),s._captureStackTrace(),o&&o._popContext();var p=!0,f=c.tryCatch(r).call(t,i,a);return p=!1,s&&f===l&&(s._rejectCallback(f.e,!0,!0),s=null),u}var c=t("./util"),l=c.errorObj,u=c.isObject,p={}.hasOwnProperty;return r}},{"./util":21}],21:[function(t,e,n){"use strict";function r(){try{var t=R;return R=null,t.apply(this,arguments)}catch(e){return x.e=e,x}}function o(t){return R=t,r}function i(t){return null==t||t===!0||t===!1||"string"==typeof t||"number"==typeof t}function a(t){return"function"==typeof t||"object"==typeof t&&null!==t}function s(t){return i(t)?new Error(v(t)):t}function c(t,e){var n,r=t.length,o=new Array(r+1);for(n=0;r>n;++n)o[n]=t[n];return o[n]=e,o}function l(t,e,n){if(!F.isES5)return{}.hasOwnProperty.call(t,e)?t[e]:void 0;var r=Object.getOwnPropertyDescriptor(t,e);return null!=r?null==r.get&&null==r.set?r.value:n:void 0}function u(t,e,n){if(i(t))return t;var r={value:n,configurable:!0,enumerable:!1,writable:!0};return F.defineProperty(t,e,r),t}function p(t){throw t}function f(t){try{if("function"==typeof t){var e=F.names(t.prototype),n=F.isES5&&e.length>1,r=e.length>0&&!(1===e.length&&"constructor"===e[0]),o=A.test(t+"")&&F.names(t).length>0;if(n||r||o)return!0}return!1}catch(i){return!1}}function h(t){function e(){}function n(){return typeof r.foo}e.prototype=t;var r=new e;return n(),n(),t}function d(t){return H.test(t)}function _(t,e,n){for(var r=new Array(t),o=0;t>o;++o)r[o]=e+o+n;return r}function v(t){try{return t+""}catch(e){return"[no string representation]"}}function y(t){return t instanceof Error||null!==t&&"object"==typeof t&&"string"==typeof t.message&&"string"==typeof t.name}function g(t){try{u(t,"isOperational",!0)}catch(e){}}function m(t){return null==t?!1:t instanceof Error.__BluebirdErrorTypes__.OperationalError||t.isOperational===!0}function b(t){return y(t)&&F.propertyIsWritable(t,"stack")}function C(t){return{}.toString.call(t)}function w(t,e,n){for(var r=F.names(t),o=0;o<r.length;++o){var i=r[o];if(n(i))try{F.defineProperty(e,i,F.getDescriptor(t,i))}catch(a){}}}function k(t){return I?process.env[t]:void 0}function E(){if("function"==typeof Promise)try{var t=new Promise(function(){});if("[object Promise]"===C(t))return Promise}catch(e){}}function j(t,e){if(null===t||"function"!=typeof e||e===D)return e;null!==t.domain&&(e=t.domain.bind(e));var n=t.async;if(null!==n){var r=e;e=function(){var t=new Array(2).concat([].slice.call(arguments));return t[0]=r,t[1]=this,n.runInAsyncScope.apply(n,t)}}return e}var F=t("./es5"),T="undefined"==typeof navigator,x={e:{}},R,S="undefined"!=typeof self?self:"undefined"!=typeof window?window:"undefined"!=typeof global?global:void 0!==this?this:null,P=function(t,e){function n(){this.constructor=t,this.constructor$=e;for(var n in e.prototype)r.call(e.prototype,n)&&"$"!==n.charAt(n.length-1)&&(this[n+"$"]=e.prototype[n])}var r={}.hasOwnProperty;return n.prototype=e.prototype,t.prototype=new n,t.prototype},O=function(){var t=[Array.prototype,Object.prototype,Function.prototype],e=function(e){for(var n=0;n<t.length;++n)if(t[n]===e)return!0;return!1};if(F.isES5){var n=Object.getOwnPropertyNames;return function(t){for(var r=[],o=Object.create(null);null!=t&&!e(t);){var i;try{i=n(t)}catch(a){return r}for(var s=0;s<i.length;++s){var c=i[s];if(!o[c]){o[c]=!0;var l=Object.getOwnPropertyDescriptor(t,c);null!=l&&null==l.get&&null==l.set&&r.push(c)}}t=F.getPrototypeOf(t)}return r}}var r={}.hasOwnProperty;return function(n){if(e(n))return[];var o=[];t:for(var i in n)if(r.call(n,i))o.push(i);else{for(var a=0;a<t.length;++a)if(r.call(t[a],i))continue t;o.push(i)}return o}}(),A=/this\s*\.\s*\S+\s*=/,H=/^[a-z$_][a-z$_0-9]*$/i,N=function(){return"stack"in new Error?function(t){return b(t)?t:new Error(v(t))}:function(t){if(b(t))return t;try{throw new Error(v(t))}catch(e){return e}}}(),L=function(t){return F.isArray(t)?t:null};if("undefined"!=typeof Symbol&&Symbol.iterator){var B="function"==typeof Array.from?function(t){return Array.from(t)}:function(t){for(var e,n=[],r=t[Symbol.iterator]();!(e=r.next()).done;)n.push(e.value);return n};L=function(t){return F.isArray(t)?t:null!=t&&"function"==typeof t[Symbol.iterator]?B(t):null}}var U="undefined"!=typeof process&&"[object process]"===C(process).toLowerCase(),I="undefined"!=typeof process&&"undefined"!=typeof process.env,D,V={setReflectHandler:function(t){D=t},isClass:f,isIdentifier:d,inheritedDataKeys:O,getDataPropertyOrDefault:l,thrower:p,isArray:F.isArray,asArray:L,notEnumerableProp:u,isPrimitive:i,isObject:a,isError:y,canEvaluate:T,errorObj:x,tryCatch:o,inherits:P,withAppended:c,maybeWrapAsError:s,toFastProperties:h,filledRange:_,toString:v,canAttachTrace:b,ensureErrorObject:N,originatesFromRejection:m,markAsOriginatingFromRejection:g,classString:C,copyDescriptors:w,isNode:U,hasEnvVariables:I,env:k,global:S,getNativePromise:E,contextBind:j};V.isRecentNode=V.isNode&&function(){var t;return process.versions&&process.versions.node?t=process.versions.node.split(".").map(Number):process.version&&(t=process.version.split(".").map(Number)),0===t[0]&&t[1]>10||t[0]>0}(),V.nodeSupportsAsyncResource=V.isNode&&function(){var e=!1;try{var n=t("async_hooks").AsyncResource;e="function"==typeof n.prototype.runInAsyncScope}catch(r){e=!1}return e}(),V.isNode&&V.toFastProperties(process);try{throw new Error}catch(Q){V.lastLineError=Q}e.exports=V},{"./es5":10,async_hooks:void 0}]},{},[3])(3)}),"undefined"!=typeof window&&null!==window?window.P=window.Promise:"undefined"!=typeof self&&null!==self&&(self.P=self.Promise);
// jshint ignore: end
	lib.Promise = Promise;
	if(!lib.nativePromise) {
		lib.nativePromise = lib.Promise;
	}

})(Dynamsoft);(function (lib) {

    "use strict";
	
	var _navInfo_ver = 20200717;

	if (lib._navInfo_ver) {
		if (lib.isNumber(lib._navInfo_ver) && lib._navInfo_ver >= _navInfo_ver) {
			return;
		}
	}
	lib._navInfo_ver = _navInfo_ver;
	
	lib.getNavInfoSync = function() {
		var FALSE = !1, TRUE = !0,
			win = lib.win,
			doc = lib.doc,
			_protocol = doc.location.protocol,
			_ssl = (_protocol === 'https:'),
			_bFileSystem = (_protocol !== 'https:' && _protocol !== 'http:'),

			_bIE = false,
			_bEdge = false,
			_bHTML5Edition = true,
			_bGecko = true,
			_bMobileOrPad = false,
			_IEVersion = 0,
			_IEMode = 0,
			_nativeJson = win.JSON;

		lib.getNavInfo();
		if('userAgentData' in navigator) {
			_bMobileOrPad = navigator['userAgentData'].mobile;
		}
		else {
			var _nav = Dynamsoft.navInfo;
			_bIE = _nav.bIE;
			_bEdge = _nav.bEdge;
			_bGecko = _nav.bGecko;
			_bMobileOrPad = _nav.bMobile || _nav.bPad || _nav.bChromeOS;
			
			if(_bIE) {
				_IEVersion = _nav.strBrowserVersion;
				_IEMode = _nav.IEMode;
			}
			
			_bHTML5Edition = _nav.bHTML5Edition;
		}

		return {
			host: win,
			bSSL: _ssl,
			bFileSystem: _bFileSystem,
			
			bIE: _bIE,
			bEdge: _bEdge,
			bGecko: _bGecko,
			
			bMobile: _bMobileOrPad,
			
			IEVersion: _IEVersion,
			IEMode: _IEMode,
			
			bHTML5Edition: _bHTML5Edition,
			nodejs: FALSE
		};
	};
	
	lib.getNavInfoByUserAgent = function(a_userAgent, a_platform) {

		var EMPTY_STR = '',
			FALSE = !1, TRUE = !0,
			win = lib.win,
			doc = lib.doc,
			docElement = doc && doc.documentElement,
			_tmp,
			
			ua = a_userAgent.toLowerCase(),
			_platform = a_platform.toLowerCase(),
			
			_bChromeOS = (/cros/).test(ua),
			_bAndroid = (/android/g).test(ua),
			_biPhone = (/iphone/g).test(ua) || (/iphone/g).test(_platform),
			
			_bPadOrMacDesktop = (/macintosh/).test(ua),	// maybe iPad or MAC Desktop
			_biPad = (/ipad/g).test(ua) || ((_bPadOrMacDesktop||(_platform=='macintel')) && navigator.maxTouchPoints && navigator.maxTouchPoints > 1),
			
			_bUC = (/ucweb|ucbrowser/g).test(ua),
			_bNexus = !_bUC && (/nexus/g).test(ua) && (/version\/[\d.]+.*safari\//g).test(ua),

			_bPlaybook = (/playbook/g).test(ua),
			_bHpTablet = (/hp-tablet/g).test(ua),
			_bBlackBerry = (/blackberry|bb10/g).test(ua),
			_bSymbian = (/symbian/g).test(ua),
			_bWindowsPhone = (/windows phone/g).test(ua);

		var _bPad = _bPlaybook || _biPad || _bHpTablet,		
			_bMobile = _biPhone || _bNexus ||
					   _bBlackBerry || _bSymbian || _bWindowsPhone || _bAndroid,

			_bNotMobileOS = !_bMobile && !_bPad && !_bChromeOS,

			_bWin = _bNotMobileOS && (/win32|win64|windows/).test(_platform),
			_bWin64 = _bWin && (/win64|x64/).test(ua),

			_bMac = _bNotMobileOS && (/mac68k|macppc|macintosh|macintel/).test(ua),
			_bLinux = _bNotMobileOS && (/linux/).test(_platform),

			_bOSx64 = (_platform == 'win64') || (/wow64|x86_64|win64|x64/).test(ua),
			_bWOW64 = (/wow64/g).test(ua),


			// Browser capabilities
			_nMSIE = ua.indexOf('msie '),
			_nTrident = ua.indexOf('trident'),
			_nRV = ua.indexOf('rv:'),
			
			_bSafari = FALSE,
			
			_bOpera = (/opera|opr/g).test(ua),
			
			// IE like (IE7+)
			_b360SE = (/360se/g).test(ua),
			_bMaxthon = (/maxthon/g).test(ua),	// ao you
			_bTencentTraveler = (/tencenttraveler|qqbrowser/g).test(ua),	// tencent TT OR QQ Browser
			_bTheWorld = (/the world/g).test(ua),	// The World
			_bMetaSr = (/metasr/g).test(ua),	// sogou
			_bAvant = (/avant/g).test(ua),	// Avant
			
			_bFirefox = (/firefox|fxios/g).test(ua),

			_bEdge = !_bFirefox && (/edge\/|edga\/|edgios\/|edg\//g).test(ua),

			_bChrome = !(_bBlackBerry || _bPlaybook || _bUC || _bOpera || _bEdge) && (/chrome|crios/g).test(ua),

			_bIE = _bWin && !_bFirefox && !_bEdge && !_bChrome && (_nMSIE != -1 || _nTrident != -1 || _nRV != -1),
			_strIEVersion = '',
			_IEMode = 0,

			_bGecko = (/gecko/g).test(ua),

			_bHTML5Edition = _bMobile || _bPad,

			_strBrowserVersion = EMPTY_STR,
			_bQuerySelector = FALSE,
			_nativeJson = win.JSON;

		if ((_bMac || _biPhone || _biPad || _bWin || _bBlackBerry || _bPlaybook || _bNexus) && 
			!_bUC && !_bOpera && !_bEdge && !_bIE && !_bFirefox) {
				
			_tmp = ua.match(/version\/([\d.]+).*safari\//);
			if(_tmp) {
				if(_bBlackBerry || _bPlaybook || _bNexus) {
				} else {
					_bSafari = TRUE;
					_bChrome = FALSE;
				}
				_strBrowserVersion = _tmp[1];
			}
		}
			
		if (_bEdge) {
			
			var _nEdge = ua.indexOf('edge/');
			if(_nEdge>-1) {
				_nEdge += 5;
			} else {
				_nEdge = ua.indexOf('edg/');
				if(_nEdge>-1) {
					_nEdge += 4;
				} else {
					_nEdge = ua.indexOf('edga/');
					if(_nEdge>-1) {
						_nEdge += 5;
					} else {
						_nEdge = ua.indexOf('edgios/');
						if(_nEdge>-1) {
							_nEdge += 7;
						}
					}
				}
			}
			
			if(_nEdge>-1) {
				_strBrowserVersion = ua.slice(_nEdge);
				_tmp = _strBrowserVersion.indexOf(' ');
				if(_tmp>-1)
					_strBrowserVersion = _strBrowserVersion.slice(0, _tmp);
			}
			
			_bHTML5Edition = TRUE;
		} else if (_bFirefox) {	// FF
			_tmp = ua.indexOf('firefox/');
			_bHTML5Edition = TRUE;	// default is HTML5 Edition
			
			if(_tmp>-1) {

				_tmp = ua.slice(_tmp + 8);
				
				var _tmp2 = _tmp.indexOf(' ');
				if(_tmp2>-1)
					_tmp = _tmp.slice(0, _tmp2);
				
				_strBrowserVersion = _tmp;

				_tmp2 = _tmp.indexOf('.');
				if(_tmp2>-1)
					_tmp = _strBrowserVersion.slice(0, _tmp2);
				
				if (_tmp < 27) {
					_bHTML5Edition = FALSE;
				}
				
			} else if (_biPhone || _biPad){
				_tmp = ua.indexOf('fxios/');
				if(_tmp>-1) {
					_tmp = ua.slice(_tmp + 6);
					_tmp = _tmp.slice(0, _tmp.indexOf(' '));
					_strBrowserVersion = _tmp;
				}
			}

			
		} else if (_bIE) {
			if (_nMSIE != -1) {
				// 'msie'
				_tmp = ua.slice(_nMSIE + 5);
				_tmp = _tmp.slice(0, _tmp.indexOf(';'));
				_strIEVersion = _tmp;
			} else if (_nRV != -1) {
				// 'rv:'
				_tmp = ua.slice(_nRV + 3);
				_tmp = _tmp.slice(0, _tmp.indexOf(';'));
				_tmp = _tmp.slice(0, _tmp.indexOf(')'));
				_strIEVersion = _tmp;
			} else if (_nTrident != -1) {
				// 'trident'
				_tmp = ua.slice(_nTrident + 7);
				_tmp = _tmp.slice(0, _tmp.indexOf(';'));
				_strIEVersion = _tmp;
			}

			if (_strIEVersion === '' || _strIEVersion > 8.0) {
				_bHTML5Edition = TRUE;
			}

			_strBrowserVersion = _tmp;

		} else if (_bSafari) {
			_tmp = _strBrowserVersion.indexOf('.');

			// safari
			_bHTML5Edition = TRUE;
			
			if (_tmp > -1) {
				_tmp = _strBrowserVersion.slice(0, _tmp);
				if (_tmp < 7) {
					_bHTML5Edition = FALSE;
				}
			}
			
		} else if (_bUC) {
			// uc
			_tmp = ua.indexOf('ucweb');
			if(_tmp > -1)
				_strBrowserVersion = ua.slice(_tmp + 5);
			else {
				_tmp = ua.indexOf('ucbrowser/');
				if(_tmp > -1) {
					_strBrowserVersion = ua.slice(_tmp + 10);
					_tmp = _strBrowserVersion.indexOf(' ');
					if(_tmp>-1) {
						_strBrowserVersion = _strBrowserVersion.slice(0, _tmp);
					}
				}
			}
			_bHTML5Edition = TRUE;
		} else if (_bOpera) {
			// opera
			_tmp = ua.indexOf('version/');
			if(_tmp > -1)
				_strBrowserVersion = ua.slice(_tmp + 8);
			else {
				_tmp = ua.indexOf('opr/');
				if(_tmp > -1)
					_strBrowserVersion = ua.slice(_tmp + 4);
			}
			_bHTML5Edition = TRUE;
		} else if (_bSymbian) {
			_tmp = ua.indexOf('browserng/'); // Nokia N97, SymbianOS
			if(_tmp > -1)
				_strBrowserVersion = ua.slice(_tmp + 10);
			_bHTML5Edition = TRUE;
		} else if (_bWindowsPhone) {
			_tmp = ua.indexOf('iemobile/');
			if(_tmp > -1)
				_strBrowserVersion = ua.slice(_tmp + 9);
			_bHTML5Edition = TRUE;
		} else if (_bChrome) {
			
			var _nChrome = ua.indexOf('chrome/');
			
			if(_nChrome>-1) {
				_strBrowserVersion = ua.slice(_nChrome + 7);
				_tmp = _strBrowserVersion.indexOf(' ');
				if(_tmp>-1)
					_strBrowserVersion = _strBrowserVersion.slice(0, _tmp);
			} else {
				_nChrome = ua.indexOf('crios/');
				if(_nChrome>-1) {
					_strBrowserVersion = ua.slice(_nChrome + 6);
					_tmp = _strBrowserVersion.indexOf(' ');
					if(_tmp>-1)
						_strBrowserVersion = _strBrowserVersion.slice(0, _tmp);
				}
			}
			
			_bHTML5Edition = TRUE;
			
			_tmp = _strBrowserVersion.indexOf('.');
			if (_tmp > -1) {
				_tmp = _strBrowserVersion.slice(0, _tmp);
				if (_tmp < 27) {
					_bHTML5Edition = FALSE;
				}
			}
		}

		if (_bEdge || _bIE) {
			// This is an IE browser. What mode is the engine in?
			if (doc.documentMode) {
				// IE8 or later
				_IEMode = doc.documentMode;
			}
			else // IE 5-7
			{
				_IEMode = 5; // Assume quirks mode unless proven otherwise
				if (doc.compatMode) {
					if (doc.compatMode == "CSS1Compat")
						_IEMode = 7; // standards mode
				}
				// There is no test for IE6 standards mode because that mode  
				// was replaced by IE7 standards mode; there is no emulation.
			}
		}

		if (docElement && docElement.querySelector && (!_bIE || _bIE && (_strBrowserVersion > 8))) {
			_bQuerySelector = TRUE;
		}

		// ie 8.0.7600.16315@win7 json bug!
		if (_bIE && _strBrowserVersion < 9) {
			_nativeJson = null;
		}

		return {

			bWin: _bWin,
			bMac: _bMac,
			bLinux: _bLinux,
			bMobile: _bMobile,		// contains iPhone/Android/WindowsPhone/Nexus/BlackBerry/Symbian
			bPad: _bPad,
			bChromeOS: _bChromeOS,
			
			bAndroid: _bAndroid,
			biPhone: _biPhone,
			biPad: _biPad,

			bWin64: _bWin64,				// ua is win64 or x64
			bWOW64: _bWOW64,				// ua is wow64
			bOSx64: _bOSx64,			// platform win64 or ua is wow64 | x86_64 | win64 | x64

			bIE: _bIE,
			bEdge: _bEdge,
			bChrome: _bChrome,
			bFirefox: _bFirefox,
			bSafari: _bSafari,
			bOpera: _bOpera,

			bNexus: _bNexus,
			bUC: _bUC,
			b360SE: _b360SE,
			bMaxthon: _bMaxthon,	// ao you
			bTencentTraveler: _bTencentTraveler,	// tencent TT OR QQ Browser
			bTheWorld: _bTheWorld,	// The World
			bMetaSr: _bMetaSr,	// sogou
			bAvant: _bAvant,	// Avant

			bGecko: _bGecko,

			bHTML5Edition: _bHTML5Edition,

			strBrowserVersion: _strBrowserVersion,
			IEMode: _IEMode,
			bQuerySelectorSupported: _bQuerySelector,
			nativeJson: _nativeJson,
			scrollBarWidth: FALSE
		};
	};
	
	lib.getNavInfoByUAData = function(a_highEntData){
		
		var fnGetNavInfo = function(highEntData){
			
			var uaData = navigator['userAgentData'],
				_bMobile = uaData.mobile,
				_browser,
				_browserVersion,
				_platform = highEntData.platform.toLowerCase(),				// Windows
				_platformVersion = highEntData.platformVersion,             // "10.0; "         (win10)
				_architecture = highEntData.architecture.toLowerCase(),
				_bOSx64 = false,
				_bMac = (_platform.indexOf('mac')>=0);
				
			if('brands' in uaData && lib.isArray(uaData['brands'])) {
				_browser = uaData.brands[0].brand.toLowerCase();
				_browserVersion = uaData.brands[0].version;
			} else if('uaList' in uaData && lib.isArray(uaData['uaList'])) {
				_browser = uaData.uaList[0].brand.toLowerCase();
				_browserVersion = uaData.uaList[0].version;
			}
			
			if(_bMac) {
				var aryVer = _platformVersion.split('_');
				if(aryVer.length>0 && aryVer[0]>=15) {
					_bOSx64 = true;	
				}
			} else if(_architecture.indexOf('win64')>=0 || _architecture.indexOf('x86_64')>=0 || _architecture.indexOf('x64')>=0) {
				_bOSx64 = true;				// x86_64 | win64 | x64
			}
			
			return {

				bWin: (_platform == 'windows'),
				bMac: _bMac,
				bLinux: (_platform == 'linux'),
				bAndroid: false,
				bMobile: _bMobile,
				bPad: false,
				bChromeOS: false,

				bOSx64: _bOSx64,

				bIE: false,
				bEdge: false,
				bChrome: true,
				bFirefox: false,
				bSafari: false,
				bOpera: false,
				bGecko: true,

				bHTML5Edition: true,

				strBrowserVersion: _browserVersion,
				IEMode: false,
				bQuerySelectorSupported: true,
				nativeJson: true,
				scrollBarWidth: false
			};	
		};
		
		if(a_highEntData) {
			return Promise.resolve(function(){
				return fnGetNavInfo(a_highEntData);
			});
		}
		
		return navigator['userAgentData']
			.getHighEntropyValues([
				"platform",         // Windows
				"platformVersion", 	// "10.0; "         (win10)
				"architecture" 		// Win64; x64
			])
			.then(fnGetNavInfo);
	};

	lib.asyncGetNavInfo = function(){
		if(Dynamsoft.navInfo) {
			return Promise.resolve(Dynamsoft.navInfo);
		}
		
		if('userAgentData' in navigator) {
			return lib.getNavInfoByUAData().then(function(_navInfo){
				Dynamsoft.navInfo = _navInfo;
				return _navInfo;
			});
		} else {
			// by old userAgent
			var nav = navigator;
			Dynamsoft.navInfo = lib.getNavInfoByUserAgent(nav.userAgent, nav.platform);
			return Promise.resolve(Dynamsoft.navInfo);
		}
	};
	
	lib.getNavInfo = function(){
		if(Dynamsoft.navInfo)
			return Dynamsoft.navInfo;
		
		if('userAgentData' in navigator) {
			lib.getNavInfoByUAData().then(function(_navInfo){
				Dynamsoft.navInfo = _navInfo;
			});
			return false;
			
		} else {
			// by old userAgent
			var nav = navigator;
			Dynamsoft.navInfo = lib.getNavInfoByUserAgent(nav.userAgent, nav.platform);
			return Dynamsoft.navInfo;
		}
	};

	Dynamsoft.navInfoSync = lib.getNavInfoSync();
	
})(Dynamsoft.Lib);
/// File Description:
/// 	XmlHttpRequest wrapper.
///

(function (dynam, nil) {

	"use strict";
	var lib = dynam.Lib,
		navInfoSync = dynam.navInfoSync,
		_ls_ver = 20200521;

	if (lib._ls_ver) {
		if (lib.isNumber(lib._ls_ver) && lib._ls_ver >= _ls_ver) {
			return;
		}
	}
	lib._ls_ver = _ls_ver;
	
	var _bEnable = false, _LS=false, _ret;

	if ((navInfoSync.bEdge && navInfoSync.bFileSystem) || 
		(navInfoSync.bIE && navInfoSync.IEVersion<8)) {
		// when Edge && File Mode, not using localStorage
	} else {
		try {
			_LS = window['localStorage'];	// jshint ignore: line
			_bEnable = _LS ? true : false;
		} catch (e) { 
			_LS = false;
		}
	}
	
	// add local Storage
	lib.LS = {
		isSupportLS: function () {
			return _bEnable;
		},

		item: function (name, value, nil) {
			var val = null;
			if (this.isSupportLS()) {
				if (value) {
					_LS.setItem(name, value);
					val = value;
				} else {
					val = _LS.getItem(name);
				}

				if (val === null)
					return nil;

				return val;
			} else {
				return nil;
			}

		},

		removeItem: function (name) {
			if (this.isSupportLS()) {
				_LS.removeItem(name);
			} else {
				return false;
			}
			return true;
		}
	};

})(Dynamsoft);
/// File Description:
/// 	Utilities for DWS internal use.
///


// common api
(function (lib, nil) {
    "use strict";

    var _utilities_ver = 20200708;
    if (lib._utilities_ver) {
        if (lib._utilities_ver >= _utilities_ver) {
            return;
        }
    }
    lib._utilities_ver = _utilities_ver;

	var AP = Array.prototype,
        win = lib.win,
        doc = lib.doc,
		navInfoSync = Dynamsoft.navInfoSync,
        EMPTY_STR = '',
        FALSE = !1, TRUE = !0,
        mix = lib.mix;

    // global functions
    var RE_TRIM = /^[\s\xa0]+|[\s\xa0]+$/g,
        indexOf = AP.indexOf,
        lastIndexOf = AP.lastIndexOf,
        filter = AP.filter,
        every = AP.every,
        some = AP.some,
        map = AP.map;

    var logger = lib.getLogger(),
        location = win.location,
        bDomReady = 0,
        callbacks = [],
        // The number of poll times.
        POLL_RETIRES = 500,
        // The poll interval in milliseconds.
        POLL_INTERVAL = 40,
        // #id or id
        RE_ID_STR = /^#?([\w-]+)$/,
        RE_NOT_WHITESPACE = /\S/,
        standardEventModel = !!(doc && doc.addEventListener),
        DOM_READY_EVENT = 'DOMContentLoaded',
        READY_STATE_CHANGE_EVENT = 'readystatechange',
        LOAD_EVENT = 'load',
        COMPLETE = 'complete',
        addEventListener = standardEventModel ? function (el, type, fn) {
            el.addEventListener(type, fn, false);
        } : function (el, type, fn) {
            el.attachEvent('on' + type, fn);
        },
        removeEventListener = standardEventModel ? function (el, type, fn) {
            el.removeEventListener(type, fn, false);
        } : function (el, type, fn) {
            el.detachEvent('on' + type, fn);
        };

    lib.mix(lib, {
        isWindow: function (obj) {
            // must use == for ie8
            /*jshint eqeqeq:false*/
            return obj != null && obj == obj.window;
        },
        globalEval: function (data) {
            if (data && RE_NOT_WHITESPACE.test(data)) {
                // http://weblogs.java.net/blog/driscoll/archive/2009/09/08/eval-javascript-global-context
                // http://msdn.microsoft.com/en-us/library/ie/ms536420(v=vs.85).aspx always return null
                /*jshint evil:true*/
                if (win.execScript) {
                    win.execScript(data);
                } else {
                    (function (data) {
                        win.eval.call(win, data);
                    })(data);
                }
            }
        },

        domReady: function (fn) {
            if (bDomReady) {
                try {
                    fn(lib);
                } catch (e) {
                    lib.log(e.stack || e, 'error');
                    setTimeout(function () {
                        throw e;
                    }, 0);
                }
            } else {
                callbacks.push(fn);
            }
            return this;
        }
    });

	// [deprecated] compatible
	lib.ready = lib.domReady;

    function fireReady() {

        for (var i = 0; i < callbacks.length; i++) {
            try {
                callbacks[i](lib);
            } catch (e) {
                lib.log(e.stack || e, 'error');
                /*jshint loopfunc:true*/
                setTimeout(function () {
                    throw e;
                }, 0);
            }
        }
    }
	
	lib.checkDomReady = function() {

        if (!bDomReady) {
			
			bDomReady = 1;
			lib.asyncGetNavInfo().then(function(navInfo){
				// nodejs
				if (doc && !navInfoSync.nodejs) {
					removeEventListener(win, LOAD_EVENT, lib.checkDomReady);
				}
				fireReady();
			});
		}

	};

    //  Binds ready events.
    function bindReady() {
        // Catch cases where ready() is called after the
        // browser event has already occurred.
        if (!doc || doc.readyState === COMPLETE) {
            lib.checkDomReady();
            return;
        }

        // A fallback to window.onload, that will always work
        addEventListener(win, LOAD_EVENT, lib.checkDomReady);

        // w3c mode
        if (standardEventModel) {
            var fnDomReady = function () {
                removeEventListener(doc, DOM_READY_EVENT, fnDomReady);
                lib.checkDomReady();
            };

            addEventListener(doc, DOM_READY_EVENT, fnDomReady);
        }
        // IE event model is used
        else {
            var stateChange = function () {
                if (doc.readyState === COMPLETE) {
                    removeEventListener(doc, READY_STATE_CHANGE_EVENT, stateChange);
                    lib.checkDomReady();
                }
            };

            // ensure firing before onload (but completed after all inner iframes is loaded)
            // maybe late but safe also for iframes
            addEventListener(doc, READY_STATE_CHANGE_EVENT, stateChange);

            // If IE and not a frame
            // continually check to see if the document is ready
            var notframe,
				docElem = doc && doc.documentElement,
                doScroll = docElem && docElem.doScroll;

            try {
                notframe = (win.frameElement === null);
            } catch (e) {
                notframe = false;
            }

            // can not use in iframe,parent window is dom ready so doScroll is ready too
            if (doScroll && notframe) {
                var readyScroll = function () {
                    try {
                        // Ref: http://javascript.nwbox.com/IEContentLoaded/
                        doScroll('left');
                        setTimeout(lib.checkDomReady, 30);
                    } catch (ex) {
                        setTimeout(readyScroll, POLL_INTERVAL);
                    }
                };
                readyScroll();
            }
        }
    }

    // bind on start
    // in case when you bind but the DOMContentLoaded has triggered
    // then you has to wait onload
    // worst case no callback at all
    bindReady();

    if (Dynamsoft.navInfoSync.bIE) {
        try {
            doc.execCommand('BackgroundImageCache', false, true);
        } catch (e) {
        }
    }

})(Dynamsoft.Lib);

(function (lib) {
    "use strict";

    var _domUtil_ver = 20200521;
    if (lib._domUtil_ver) {
        if (lib._domUtil_ver >= _domUtil_ver) {
            return;
        }
    }
    lib._domUtil_ver = _domUtil_ver;
	
    var EMPTY_STR = '', NONE_STR = 'none';
    // simple DOM functions
    lib.mix(lib, {
        get: function (id) {
            return lib.doc.getElementById(id);
        },

        hide: function (id) {
            var o = lib.isString(id) ? lib.get(id) : id;

            if (o) {
                o.style.display = NONE_STR;
            }
        },

        show: function (id) {
            var o = lib.isString(id) ? lib.get(id) : id;

            if (o) {
                o.style.display = EMPTY_STR;
            }
        },

        toggle: function (id) {
            var o = lib.isString(id) ? lib.get(id) : id;

            if (o) {
                if (o.style.display === NONE_STR)
                    o.style.display = EMPTY_STR;
                else
                    o.style.display = NONE_STR;
            }
        },

        empty: function (el) {
            if (!el) return;

            while (el.firstChild) {
                el.removeChild(el.firstChild);
            }
        }
    });
})(Dynamsoft.Lib);(function (dynam) {
    "use strict";
	var lib = dynam.Lib;

	var _color_ver = 20200521;
	if (lib._color_ver) {
		if (lib.isNumber(lib._color_ver) && lib._color_ver >= _color_ver) {
			return;
		}
	}
	lib._color_ver = _color_ver;
	
	lib.colorStrToInt = function (str) {
		var mystr = "0x", hex, i;

		if (/^(rgb|RGB)/.test(str)) {
			var nums = str.replace(/[^\d,.]/g, "").split(",");
			for (i = 0; i < 3; ++i) {
				hex = Number(nums[i]).toString(16);
				if (hex.length == 1) {
					hex = "0" + hex;
				}
				mystr += hex;
			}
			if (nums.length == 4) {
				// rgba
				hex = Math.round(Number(nums[i]) * 0xff).toString(16);
				if (hex.length == 1) {
					hex = "0" + hex;
				}
				mystr += hex;
			} else {
				// rgb
				mystr += "ff";
			}
		} else if (str == "transparent") {
			// transparent
			mystr += "00000000";
		} else if (/^#[0-9a-fA-f]{6}$/.test(str)) {
			// #ffffff
			mystr += str.replace(/#/, "") + "ff";
		} else if (/^#[0-9a-fA-f]{3}$/.test(str)) {
			// #fff
			for (i = 0; i < 3; ++i) {
				mystr += str[i] + str[i];
			}
			mystr += "ff";
		} else {
			mystr = "-1";
		}
		return Number(mystr);
	};

	lib.IntToColorStr = function (value) {
		if (value > 0xffffffff || value < 0x00000000) {
			// out of range, return null
			return null;
		}
		var str;
		if (!Dynamsoft.navInfoSync.bHTML5Edition) {
			// below ie 8
			if (value % 0x100 == 0) {
				str = "transparent";
			} else {
				str = Math.floor(value / 0x100).toString(16);
				while (str.length != 6) {
					str = '0' + str;
				}
				str = '#' + str;
			}
		} else {
			// up ie 9
			str = "rgba(" +
				Math.floor(value / 0x1000000) + "," +
				Math.floor(value / 0x10000) % 0x100 + "," +
				Math.floor(value / 0x100) % 0x100 + "," +
				(value % 0x100) / 0xff + ")";
		}
		return str;
	};

})(Dynamsoft);/// File Description:
/// 	XmlHttpRequest wrapper.
///

(function (dynam, nil) {

	"use strict";
	var lib = dynam.Lib,
		_ajax_ver = 20200716;
		
	if (lib._ajax_ver) {
		if (lib.isNumber(lib._ajax_ver) && lib._ajax_ver >= _ajax_ver) {
			return;
		}
	}
	lib._ajax_ver = _ajax_ver;
	
lib.asyncGetNavInfo().then(function(navInfo){

	var bIE6_9 = navInfo.bIE && (parseInt(navInfo.strBrowserVersion) <= 9),
		bIE6_10 = navInfo.bIE && (parseInt(navInfo.strBrowserVersion) <= 10),
		win = lib.win,
		each = lib.each,
		rlocalProtocol = /^(?:about|app|app\-storage|.+\-extension|file|widget)$/,

		STATE_READY = 1,
		STATE_OK = 2,
		STATE_ABORT = 3,

		OK_CODE = 200,
		NO_CONTENT_CODE = 204,
		MULTIPLE_CHOICES = 300,
		NOT_MODIFIED = 304,
		NOT_FOUND_CODE = 404,
		NO_CONTENT_CODE2 = 1223,
		SERVER_ERR = 500,

		_strOpenErr = 'open error: ',
		_strSendErr = 'send error: ',

		simulatedLocation = new lib.Uri(location.href),
		isLocal = simulatedLocation && rlocalProtocol.test(simulatedLocation.getScheme()),
		XDomainRequest_ = false,//bIE6_9 && win.XDomainRequest,

		createStandardXHR = function () {
			try {
				return new win.XMLHttpRequest();
			} catch (e) {
			}
			// return undefined;
		},

		createActiveXHR = function () {
			try {
				var http = false;
				// code for IE9,IE8,IE7,IE6,IE5
				each(['Msxml2.XMLHTTP.6.0',
					'Msxml2.XMLHTTP',
					'Microsoft.XMLHTTP',
					'Msxml2.XMLHTTP.3.0',
					'Msxml3.XMLHTTP'],
					function (item) {
						try {
							return (http = new win.ActiveXObject(item));
						}
						catch (e) {
							lib.error('new xhr error: ' + e.message);
						}
					});
				return http;
			} catch (e) {
			}
			// return undefined;
		},

		supportCORS = (!isLocal && win.XMLHttpRequest) ? ('withCredentials' in (createStandardXHR() || [])) : false,

		//Create a xmlHttpRequest object
		_newXhr = win.ActiveXObject ? function (crossDomain) {

			if (bIE6_9)
				return createActiveXHR();

			if (!supportCORS && crossDomain && XDomainRequest_) {
				return new XDomainRequest_();
			}
			return !isLocal && createStandardXHR() || createActiveXHR();

		} : createStandardXHR,

		isInstanceOfXDomainRequest = function (xhr) {
			return XDomainRequest_ && (xhr instanceof XDomainRequest_);
		},

		rnoContent = /^(?:GET|HEAD)$/,
		rheaders = /^(.*?):[ \t]*([^\r\n]*)\r?$/mg,
		accepts = { 'xml': "application/xml, text/xml", 'html': "text/html", 'text': "text/plain", 'json': "application/json, text/javascript", "*": "*/*" },
		nilFun = nil,
		nativeFetch;
	
	if(self && self.fetch) {
		nativeFetch = self.fetch;
	} else {
		nativeFetch = win.fetch;
	}

	// IE<=8 fixed
	if (bIE6_10) {
		nilFun = lib.noop;
	}

	function _io() { }

	lib.mix(_io.prototype, {

		url: false, //URL to be loaded
		onSuccess: false, //Function that should be called at success
		onError: false, //Function that should be called at error
		onComplete: false,
		method: "GET", //GET or POST	
		async: true, // async or sync
		xhrFields: false,
		mimeType: false,
		username: false,
		password: false,
		data: false,
		dataType: 'text', //Return type - could be 'blob', 'arraybuffer', 'text', 'xml', 'json', 'user-defined'(which is used for acquiring image data from service)
		headers: false,
		contentType: 'application/x-www-form-urlencoded; charset=UTF-8',
		beforeSend: false,
		afterSend: false,
		timeout: 0,		// seconds		default 0 means no timeout
		cache: true,
		crossDomain: false,
		retry: 0,

		setRequestHeader: function (name, value) {
			var self = this;
			self.headers[name] = value;
			return self;
		}, getAllResponseHeaders: function () {
			var self = this;
			return self.state === STATE_OK ? self.responseHeadersString : null;
		}, getNativeXhr: function () {
			var self = this;
			return self.nativeXhr;
		}, getResponseHeader: function (name) {
			var match, self = this, responseHeaders;
			name = name.toLowerCase();
			if (self.state === STATE_OK) {
				if (!(responseHeaders = self.responseHeaders)) {
					responseHeaders = self.responseHeaders = {};
					while ((match = rheaders.exec(self.responseHeadersString))) {
						responseHeaders[match[1].toLowerCase()] = match[2];
					}
				}
				match = responseHeaders[name];
			}
			return match === undefined ? null : match;
		}, overrideMimeType: function (type) {
			var self = this;
			if (!self.state) {
				self.mimeType = type;
			}
			return self;
		}, abort: function (statusText) {
			var self = this;
			statusText = statusText || "abort";

			self.state = STATE_ABORT;
			self.status = 0;
			self.statusText = statusText;

			if (self.nativeXhr) {
				self.nativeXhr.abort();
			}

			self._callback();
			return self;
		}, _ioReady: function (status, statusText) {
			var self = this, isSuccess = false;
			if (self.state === STATE_OK || self.state === STATE_ABORT) {
				return;
			}
			if (self.state === STATE_READY)
				self.state = STATE_OK;
			self.readyState = 4;

			if (status >= OK_CODE && status < MULTIPLE_CHOICES || status === NOT_MODIFIED) {
				if (status === NOT_MODIFIED) {
					statusText = "not modified";
					isSuccess = true;
				} else {
					statusText = "success";
					isSuccess = true;
				}
			} else {
				if (status < 0) {
					status = 0;
				}
			}

			try {
				if (status >= OK_CODE)
					self.handleResponseData();
			} catch (e) {
				lib.error(e.stack || e, "error");
				statusText = e.message || "parser error";
			}
			
			
			if (status < OK_CODE || !isSuccess) {
				if(self.retry > 0) {
					self.retry = self.retry - 1;
					setTimeout(function(){
						self.sendInternal();
					}, 200);
					return;
				}
			}

			self.status = status;
			self.statusText = statusText;
			self._callback(isSuccess);
		},
		_callback: function (isSuccess) {
			var self = this, timeoutTimer = self.timeoutTimer;
			if (timeoutTimer) {
				clearTimeout(timeoutTimer);
				self.timeoutTimer = 0;
			}

			each([isSuccess ? self.onSuccess : self.onError, self.onComplete], function (func) {
				if (lib.isFunction(func)) {
					func.apply(self.context, [self.responseData, self.statusText, self]);
				}
			});

			self.responseData = null;
		},
		handleResponseData: function () {
			var self = this, result, dataType = self.dataType, nativeXhr = self.nativeXhr;

			if (dataType === 'blob' || dataType === 'arraybuffer') {
				
				if (bIE6_9) {
					// IE<=9
					var res,len;

					if('responseBody' in nativeXhr) {
						res = nativeXhr.responseBody;
						len = dsVbsBinGetLength(res);
						result = (new VBArray(dsVbsBinGetBytes(res,0,len))).toArray();
					} else {
						var i;
						result=[];
						res = nativeXhr.responseText;
						len=res.length;
						for (i=0; i<len; ++i) {
						    result.push(res.charCodeAt(i) & 0xff);  // byte at offset i
						}
					}
					
					res = null;
				}
				else if(!!win.Blob)
					result = nativeXhr.response;
				else if('responseBody' in nativeXhr)
					result = nativeXhr.responseBody;
				else
					result = nativeXhr.responseText;

			} else if (dataType == 'json') {
				if (nativeXhr.responseType && nativeXhr.responseType.toLowerCase() == 'json') {
					result = nativeXhr.response;
				} else {
					result = nativeXhr.responseText ?
						(((win.JSON && win.JSON.parse)? win.JSON.parse : lib.parse)(nativeXhr.responseText)) :
						{};
				}
			} else if (dataType === 'user-defined') {
				result = nativeXhr.response !== undefined ? nativeXhr.response : nativeXhr.responseText;
			} else {	// text or xml
				self.responseText = result = nativeXhr.responseText || '';
				try {
					var xml = nativeXhr.responseXML;
					if (xml && xml.documentElement /*#4958#*/) {
						self.responseXML = xml;
					}
				} catch (e) { }
			}

			self.responseData = result;
		},

		sendInternal: function (opt) {
			//The XMLHttpRequest object is recreated at every call - to defeat Cache problem in IE
			var self = this, c, i,
				method, url, dataType, contentType,
				nativeXhr, xhrFields, mimeType, requestHeaders,
				hasContent, sendContent;

			c = self._setup(opt);

			method = c.method;
			if(lib.isString(method)) {
				method = method.toUpperCase();
			}
			
			if(method == 'POST') {
				contentType = c.contentType;
			} else {
				contentType = false;
			}
			
			url = c.url;
			dataType = c.dataType;
			mimeType = c.mimeType;

			if (!lib.isString(url)) return;

			self.nativeXhr = nativeXhr = _newXhr(c.crossDomain);
			if (!nativeXhr) return;

			try {
				self.state = STATE_READY;

				if (c.username) {
					nativeXhr.open(method, url, c.async, c.username, c.password);
				} else {
					nativeXhr.open(method, url, c.async);
				}

				if ((c.async || navInfo.bIE) && dataType && dataType != 'user-defined' && ('responseType' in nativeXhr)) {
					try {
						nativeXhr.responseType = dataType;
					} catch (e) { }
				}

			} catch (ex) {
				if (self.state < 2) {
					lib.error(ex.stack || ex, "error");
					self._ioReady(-1, _strOpenErr +
						(lib.isNumber(ex.number) ? '(' + ex.number + ')' : '') +
						(ex.message || ''));
				} else {
					lib.error(ex);
				}

				return;
			}

			xhrFields = c.xhrFields || {};
			if ('withCredentials' in xhrFields) {
				if (!supportCORS) {
					delete xhrFields.withCredentials;
				}
			}

			each(xhrFields, function(val, key){
				try {
					nativeXhr[key] = val;
				} catch (e) {
					lib.error(e);
				}
			});

			// Override mime type if supported
			if (mimeType && nativeXhr.overrideMimeType) {
				nativeXhr.overrideMimeType(mimeType);
			}

			requestHeaders = c.headers || {};
			var xRequestHeader = requestHeaders['X-Requested-With'];
			if (xRequestHeader === false) {
				delete requestHeaders['X-Requested-With'];
			}

			// ie<10 XDomainRequest does not support setRequestHeader
			if ('setRequestHeader' in nativeXhr) {

				if (contentType) {
					nativeXhr.setRequestHeader("Content-Type", c.contentType);
				}

				nativeXhr.setRequestHeader("Accept", dataType && accepts[dataType] ? accepts[dataType] + (dataType === "*" ? "" : ", */*; q=0.01") : accepts["*"]);

				
				each(requestHeaders, function(val, key){
					nativeXhr.setRequestHeader(key, val);
				});
			}
			
			if(!c.cache)
			{
				nativeXhr.setRequestHeader('If-Modified-Since', '0');
				nativeXhr.setRequestHeader('Cache-Control', 'no-cache');
			}


			hasContent = !rnoContent.test(c.method);
			sendContent = hasContent && c.data || null;

			if (hasContent && bIE6_9) {
				sendContent = c.data;
			}

			// timeout
			if (c.async && c.timeout > 0) {
				if(c.timeout<300)
					c.timeout=300;
				self.timeoutTimer = setTimeout(function () {
					self.abort("timeout");
				}, c.timeout);
			}

			try {
				self.state = STATE_READY;
				if (lib.isFunction(self.beforeSend)) {
					var r = self.beforeSend(nativeXhr, self);
					if (r === false) {
						self.abort("cancel");
						return;
					}
				}
				nativeXhr.send(sendContent);
				sendContent = null;
				c.data = null;
				if (lib.isFunction(self.afterSend))
					self.afterSend(self);
			} catch (e) {
				if (self.state < 2) {
					lib.error(e.stack || e, "error");
					self._ioReady(-1, _strSendErr + (e.message || ''));
				} else {
					lib.error(e);
				}
			}

			if (!c.async || nativeXhr.readyState === 4) {
				self._xhrCallback();
			} else {
				if (isInstanceOfXDomainRequest(nativeXhr)) {
					nativeXhr.onload = function () {
						nativeXhr.readyState = 4;
						nativeXhr.status = OK_CODE;
						self._xhrCallback();
					};
					nativeXhr.onerror = function () {
						nativeXhr.readyState = 4;
						nativeXhr.status = SERVER_ERR;
						self._xhrCallback();
					};
				} else {
					nativeXhr.onreadystatechange = function () {
						self._xhrCallback();
					};
				}
			}
		},

		_xhrCallback: function (evt, abort) { //Call a function when the state changes.
			var self = this, nativeXhr = self.nativeXhr;

			try {
				if (nativeXhr.readyState === 4 || abort) { //Ready State will be 4 when the document is loaded.
					if (isInstanceOfXDomainRequest(nativeXhr)) {
						nativeXhr.onerror = nilFun;
						nativeXhr.onload = nilFun;
					} else {
						nativeXhr.onreadystatechange = nilFun;
					}

					if (abort) {
						if (nativeXhr.readyState !== 4) {
							nativeXhr.abort();
						}
					} else {

						if (!isInstanceOfXDomainRequest(nativeXhr)) {
							self.responseHeadersString = nativeXhr.getAllResponseHeaders();
						}

						var status = nativeXhr.status, statusText;
						try {
							statusText = nativeXhr.statusText;
						} catch (e) {
							lib.error("xhr statusText error: ");
							lib.error(e);
							statusText = "";
						}

						self._ioReady(status, statusText);
					}
				}

			} catch (e) {
				lib.error(e.stack || e, "error");

				nativeXhr.onreadystatechange = nilFun;
				if (!abort) {
					self._ioReady(-1, e.message || "process error");
				}
			}
		},

		_setup: function (opt) {
			var self = this, dataType, i, requestHeaders, url, uri;

			if(opt) {
				self.context = opt.context;
				delete opt.context;

				if (opt instanceof _io) {
					opt = opt.config;
				}

				self.config = opt;

				url = opt.url;

				if (lib.startsWith(url, 'http://') || lib.startsWith(url, 'https://')) {
					uri = new lib.Uri(url);
				} else {
					if (lib.startsWith(url, '//')) {
						opt.url = url = 'http:' + url;
					}

					uri = simulatedLocation.resolve(url);
				}

				if (!opt.dataType)
					dataType = 'text'; //Default return type is 'text'
				else
					dataType = opt.dataType.toLowerCase();
				opt.dataType = dataType;

				if (!opt.method)
					opt.method = 'GET'; //Default method is GET
				else
					opt.method = opt.method.toUpperCase();

				if (!("crossDomain" in opt)) {
					opt.crossDomain = !uri.isSameOriginAs(simulatedLocation);
				}

				requestHeaders = opt.headers;
				for (i in requestHeaders) {
					if (lib.isUndefined(requestHeaders[i]))
						delete requestHeaders[i];
				}
				lib.mix(self, opt);
			}
			
			self.state = STATE_READY;
			return self;
		}
	});

	function _ajax(opt) {
		if (!opt || !lib.isString(opt.url)) {
			lib.log('the url is error.');
			return; //Return if a url is not provided
		}

		var self = new _io();
		self.sendInternal(opt);
		return self;
	}

	lib.mix(lib, {
		ajax: _ajax,
		io: {

			/**
			 * Communicate with the server by GET method.
			 * @param {string} url - The server url
			 * @param {function} sFun - Function that would be called when success.
			 * @param {function} fFun - Function that would be called when error.
			 * @param {string} dataType - The server response type expected. Could be 'json','blob','text','xml'. 
			 */
			get: function (url, sFun, fFun, dataType) {

				return _ajax({
					method: "GET",
					url: url,
					onSuccess: sFun,
					onError: fFun,
					dataType: dataType
				});
			},

			/**
			 * Communicate with the server by POST method.
			 * @param {string} url - The server url
			 * @param {object} data - The post data
			 * @param {function} sFun - Function that would be called when success.
			 * @param {function} fFun - Function that would be called when error.
			 * @param {string} dataType - The server response type expected. Could be 'json','blob','text','xml'. 
			 */
			post: function (url, data, sFun, fFun, dataType) {
				return _ajax({
					method: "POST",
					data: data,
					url: url,
					onSuccess: sFun,
					onError: fFun,
					dataType: dataType
				});
			},

			/**
			 * Communicate with the server by PUT method.
			 * @param {string} url - The server url
			 * @param {object} data - The post data
			 * @param {function} sFun - Function that would be called when success.
			 * @param {function} fFun - Function that would be called when error.
			 * @param {string} dataType - The server response type expected. Could be 'json','blob','text','xml'. 
			 */
			put: function (url, data, sFun, fFun, dataType) {
				return _ajax({
					method: "PUT",
					data: data,
					url: url,
					onSuccess: sFun,
					onError: fFun,
					dataType: dataType
				});
			}
		}
	});
	
		
		// Chrome or Firefox
		if(navInfo.bChrome || navInfo.bFirefox || nativeFetch) {
			
			lib.fetch = function(url, options){

				var dataType = 'text';
				if(options) {
					if(options && options.dataType) {
						dataType = options.dataType;
					}
				}

				var fetchPromise, oldPromise;

				// angular store native fetch as __zone_symbol__fetch
				fetchPromise = nativeFetch(url,options);
				
				if(Promise != lib.nativePromise) {
					// must using native Promise
					oldPromise = Promise;
					Promise = lib.nativePromise;
					fetchPromise = fetchPromise.then(function(res){
						
						Promise = oldPromise;
						
						if(res.ok) {
							return res;	
						}
						else {
							throw {'httpCode': res.status, 'errorString': res.statusText};
						}
					});
				}
				
				if(dataType == 'blob')
					fetchPromise = fetchPromise.then(function(res){ return res.blob();});
				else if(dataType == 'json')
					fetchPromise = fetchPromise.then(function(res){ return res.json();});
				else if(dataType == 'arraybuffer')
					fetchPromise = fetchPromise.then(function(res){ return res.arrayBuffer();});
				else // response USVString
					fetchPromise = fetchPromise.then(function(res){ return res.text();});

				return fetchPromise;
			};
			
			
				
		} 
		else {
			// IE / Edge / safari
			if (bIE6_9)
lib.addVBS([
"Function dsVbsBinGetAt(strBinary,iOffset)\r\n", 
" dsVbsBinGetAt=AscB(MidB(strBinary,iOffset+1,1))\r\n", 
"End Function\r\n", 

"Function dsVbsBinGetBytes(strBinary,iOffset,iLength)\r\n", 
" Dim aBytes()\r\n", 
" ReDim aBytes(iLength-1)\r\n", 
" For i=0 To iLength-1\r\n", 
"  aBytes(i)=dsVbsBinGetAt(strBinary,iOffset+i)\r\n",
" Next\r\n", 
" dsVbsBinGetBytes=aBytes\r\n", 
"End Function\r\n", 

"Function dsVbsBinGetLength(strBinary)\r\n", 
" dsVbsBinGetLength=LenB(strBinary)\r\n", 
"End Function"
].join(''));
		
			var oldPromise;

			if(Promise != lib.nativePromise) {
				// must using native Promise
				oldPromise = Promise;
				Promise = lib.nativePromise;
			}
				
			// fetch
			lib.fetch = function(url, options){

				// options
				// {
				//    mode:"cors",			  // mode: cors / no-cors / same-origin
				//    method:"post",
				//    body:'',
				//    headers:{
				//      // set send data type for body
				//    	'content-type': 'application/json'
				// 	  },
				//    dataType: 'blob',       // Return type - could be 'blob', 'arraybuffer', 'text', 'json'
				//                            // NOTE: IE<=9 'blob', 'arraybuffer' -> 'user-defined'
				
				//    cache:'reload',         // (not supported) http cache: default / no-store / reload / no-cache / force-cache / only-if-cached
				//    redirect: 'manual',     // (not supported) redirect: follow / error / manual
				//    referrer: 'client',     // (not supported) no-referrer / client / URL (string)
				//    credentials:'include'   // (not supported) if carry cookie: omit/ same-origin / include
				// };

				return new Promise(function(resolutionFunc,rejectionFunc){
					
					var sFun = function(_data, _reason, _io){
						if(oldPromise)
							Promise = oldPromise;
						resolutionFunc(_data);
					}, fFun = function(_data, _reason, _io){
						if(oldPromise)
							Promise = oldPromise;
						
						rejectionFunc({'httpCode': _io.status, 'errorString': _reason});
					}, cfg = {
						
						url: url,
						onSuccess: sFun,
						onError: fFun,
						dataType: 'text'
						
					}, bContentTypeInHeaders = false;
					
					if(options) {

						if(options.method) {
							cfg.method = options.method;
						}
						
						if(options.body) {
							cfg.data = options.body;
						}
						
						if(options.headers) {

							each(options.headers, function(val, key){
								if(key.toLowerCase() == 'content-type') {
									bContentTypeInHeaders = true;
								}

								cfg.headers[key] = val;
							});

						}
						
						if(options.dataType) {
							cfg.dataType = options.dataType;
						}
					}
					
					if(bContentTypeInHeaders) {
						cfg.contentType = false;
					}
					
					if(cfg.dataType == 'blob' && bIE6_9) {
						cfg.mimeType = 'text/plain; charset=x-user-defined';
					}
					
					lib.ajax(cfg);
				});
			};
		}

});
	
})(Dynamsoft);
(function (lib) {
    "use strict";
	
	var _customEvt_ver = 20200521;
	if (lib._customEvt_ver) {
		if (lib.isNumber(lib._customEvt_ver) && lib._customEvt_ver >= _customEvt_ver) {
			return;
		}
	}
	lib._customEvt_ver = _customEvt_ver;
	
	var customEventObj = {

		fire: function (type) {
			var self = this, args;

			self.exec = self.exec || {};
			type = type.toLowerCase();
			args = Array.prototype.slice.call(arguments, 1);
			lib.each(self.exec[type] || [], function (item) {
				var fn = item.f, ctx = item.c || self;
				try { fn.apply(ctx, args); } catch (e) { lib.log(e); }
			});
		},
		on: function (type, fn, ctx) {
			var self = this;
			self.exec = self.exec || {};
			type = type.toLowerCase();
			self.exec[type] = self.exec[type] || [];
			self.exec[type].push({ f: fn, c: ctx });
		},
		off: function (type, fn, c) {
			var self = this,
				exec = self.exec;

			if (!exec) { return; }
			if (!type) {
				self.exec = null;
				return;
			}
			type = type.toLowerCase();
			if (!fn) {
				exec[type] = null;
				return;
			}
			var arr = exec[type] || [];
			for (var i = arr.length - 1; i >= 0; i--) {
				if (arr[i] === fn) {
					arr.splice(i, 1);
				}
			}
		}
	};

	lib.obj = { customEvent: customEventObj };

})(Dynamsoft.Lib);/// File Description:
///		method: addEventListener / removeEventListener / stopPropagation / fireEvent


(function (dynam) {
    "use strict";
		
	var lib = dynam.Lib,
        FALSE = !1, TRUE = !0,
		doc = lib.win.document, _funFixType;

	var _evtBase_ver = 20200521;
	if (lib._evtBase_ver) {
		if (lib.isNumber(lib._evtBase_ver) && lib._evtBase_ver >= _evtBase_ver) {
			return;
		}
	}
	lib._evtBase_ver = _evtBase_ver;


	_funFixType = function (type) {
		return (Dynamsoft.navInfoSync.bGecko && 'mousewheel'===type)? 'DOMMouseScroll' : type;
		//"onwheel" in document.createElement("div") ? "wheel" : //     Modern browsers support "wheel"
		//_type = document.onmousewheel !== undefined ? "mousewheel" : // Webkit and IE support at least "mousewheel"
		//    "DOMMouseScroll"; // let's assume that remaining browsers are older Firefox
	};

	lib.mix(lib, {
		addEventListener: doc.addEventListener ?
			function (element, type, fn) { var _type = _funFixType(type); if (element) element.addEventListener(_type, fn, false); }
			: function (element, type, fn) { var _type = _funFixType(type); if (element) element.attachEvent('on' + _type, fn); },

		removeEventListener: doc.removeEventListener ?
			function (element, type, fn) { var _type = _funFixType(type); if (element) element.removeEventListener(_type, fn, false); }
			: function (element, type, fn) { var _type = _funFixType(type); if (element) element.detachEvent('on' + _type, fn); },
			
		// stop the default behavior of a specified event
		stopPropagation: function (evt) {
			var e = evt || window.event;
			if (e.preventDefault) e.preventDefault();
			if (e.stopPropagation) e.stopPropagation();

			e.returnValue = false;
			e.cancelBubble = true;
		},
		
		fireEvent: function (name, el) {
			var event;
			if (doc.createEvent) {
				event = doc.createEvent('HTMLEvents');
				event.initEvent(name, TRUE, TRUE);

				if (el.dispatchEvent)
					el.dispatchEvent(event);
			}
			else if (doc.createEventObject) {
				event = doc.createEventObject();
				event.bubbles = TRUE;
				event.cancelable = TRUE;
				el.fireEvent(name, event);
			}
			else {
				event = new Event(name);
				if (el.dispatchEvent)
					el.dispatchEvent(event);
			}
		}
	});

})(Dynamsoft);
// base64 & utf8
(function (lib, nil) {
    "use strict";
	var _loadbase64_ver = 20200716;
	if (lib._loadbase64_ver) {
		if (lib._loadbase64_ver >= _loadbase64_ver) {
			return;
		}
	}
	lib._loadbase64_ver = _loadbase64_ver;
	
	var _const = {
		encodeChars: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=',
		decodeChars: [-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
		-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
		-1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 62, -1, -1, -1, 63,
			52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1,
		-1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14,
			15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, -1, -1, -1, -1, -1,
		-1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40,
			41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, -1, -1, -1, -1, -1]
	};

	lib.base64 = {
		UTF16ToUTF8: function (str) {
			var res = [], len = str.length, byte1, byte2;
			for (var i = 0; i < len; i++) {
				var code = str.charCodeAt(i);
				if (code > 0x0000 && code <= 0x007F) {
					// 1 bit
					// U+00000000 - U+0000007F 0xxxxxxx
					res.push(str.charAt(i));
				} else if (code >= 0x0080 && code <= 0x07FF) {
					// 2 bits
					// U+00000080 - U+000007FF 110xxxxx 10xxxxxx
					// 110xxxxx
					byte1 = 0xC0 | ((code >> 6) & 0x1F);
					// 10xxxxxx
					byte2 = 0x80 | (code & 0x3F);
					res.push(
						String.fromCharCode(byte1),
						String.fromCharCode(byte2)
					);
				} else if (code >= 0x0800 && code <= 0xFFFF) {
					// 3 bits
					// U+00000800 - U+0000FFFF 1110xxxx 10xxxxxx 10xxxxxx
					// 1110xxxx
					byte1 = 0xE0 | ((code >> 12) & 0x0F);
					// 10xxxxxx
					byte2 = 0x80 | ((code >> 6) & 0x3F);
					// 10xxxxxx
					var byte3 = 0x80 | (code & 0x3F);
					res.push(
						String.fromCharCode(byte1),
						String.fromCharCode(byte2),
						String.fromCharCode(byte3)
					);
				} else if (code >= 0x00010000 && code <= 0x001FFFFF) {
					// 4 bits
					// U+00010000 - U+001FFFFF 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
				} else if (code >= 0x00200000 && code <= 0x03FFFFFF) {
					// 5 bits
					// U+00200000 - U+03FFFFFF 111110xx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
				} else /** if (code >= 0x04000000 && code <= 0x7FFFFFFF)*/ {
					// 6 bits
					// U+04000000 - U+7FFFFFFF 1111110x 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
				}
			}

			return res.join('');
		},
		UTF8ToUTF16: function (str) {
			var res = [],
				len = str.length,
				i, byte1, byte2, code, code2, code3, utf16;

			for (i = 0; i < len; i++) {
				code = str.charCodeAt(i);
				if (((code >> 7) & 0xFF) == 0x0) {
					// 1 bit
					// 0xxxxxxx
					res.push(str.charAt(i));
				} else if (((code >> 5) & 0xFF) == 0x6) {
					// 2 bits
					// 110xxxxx 10xxxxxx
					code2 = str.charCodeAt(++i);
					byte1 = (code & 0x1F) << 6;
					byte2 = code2 & 0x3F;
					utf16 = byte1 | byte2;
					res.push(String.fromCharCode(utf16));
				} else if (((code >> 4) & 0xFF) == 0xE) {
					// 3 bits
					// 1110xxxx 10xxxxxx 10xxxxxx
					code2 = str.charCodeAt(++i);
					code3 = str.charCodeAt(++i);
					byte1 = (code << 4) | ((code2 >> 2) & 0x0F);
					byte2 = ((code2 & 0x03) << 6) | (code3 & 0x3F);
					utf16 = ((byte1 & 0x00FF) << 8) | byte2;
					res.push(String.fromCharCode(utf16));
				} else if (((code >> 3) & 0xFF) == 0x1E) {
					// 4 bits
					// 11110xxx 10xxxxxx 10xxxxxx 10xxxxxx
				} else if (((code >> 2) & 0xFF) == 0x3E) {
					// 5 bits
					// 111110xx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
				} else /** if (((code >> 1) & 0xFF) == 0x7E)*/ {
					// 6 bits
					// 1111110x 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx 10xxxxxx
				}
			}

			return res.join('');
		},
		encode: function (_str) {
			var str = this.UTF16ToUTF8(_str),
				out = [], i = 0, len = str.length, c1, c2, c3;


			while (i < len) {
				c1 = str.charCodeAt(i++) & 0xff;
				if (i == len) {
					out.push(_const.encodeChars.charAt(c1 >> 2));
					out.push(_const.encodeChars.charAt((c1 & 0x3) << 4));
					out.push('==');
					break;
				}
				c2 = str.charCodeAt(i++);
				if (i == len) {
					out.push(_const.encodeChars.charAt(c1 >> 2));
					out.push(_const.encodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4)));
					out.push(_const.encodeChars.charAt((c2 & 0xF) << 2));
					out.push('=');
					break;
				}
				c3 = str.charCodeAt(i++);
				out.push(_const.encodeChars.charAt(c1 >> 2));
				out.push(_const.encodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4)));
				out.push(_const.encodeChars.charAt(((c2 & 0xF) << 2) | ((c3 & 0xC0) >> 6)));
				out.push(_const.encodeChars.charAt(c3 & 0x3F));
			}
			return out.join('');
		},

		encodeArray: function (_array) {
			var out = [], i = 0, len = _array.length, c1, c2, c3;

			while (i < len) {
				c1 = _array[i++] & 0xff;
				if (i == len) {
					out.push(_const.encodeChars.charAt(c1 >> 2));
					out.push(_const.encodeChars.charAt((c1 & 0x3) << 4));
					out.push('==');
					break;
				}
				c2 = _array[i++] & 0xff;
				if (i == len) {
					out.push(_const.encodeChars.charAt(c1 >> 2));
					out.push(_const.encodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4)));
					out.push(_const.encodeChars.charAt((c2 & 0xF) << 2));
					out.push('=');
					break;
				}
				c3 = _array[i++] & 0xff;
				out.push(_const.encodeChars.charAt(c1 >> 2));
				out.push(_const.encodeChars.charAt(((c1 & 0x3) << 4) | ((c2 & 0xF0) >> 4)));
				out.push(_const.encodeChars.charAt(((c2 & 0xF) << 2) | ((c3 & 0xC0) >> 6)));
				out.push(_const.encodeChars.charAt(c3 & 0x3F));
			}
			return out.join('');
		},

		decode: function (str) {

			var _this = this, out = [], i = 0, len = str.length,
				c1, c2, c3, c4;

			while (i < len) {
				/* c1 */
				do {
					c1 = _const.decodeChars[str.charCodeAt(i++) & 0xff];
				} while (i < len && c1 == -1);
				if (c1 == -1)
					break;

				/* c2 */
				do {
					c2 = _const.decodeChars[str.charCodeAt(i++) & 0xff];
				} while (i < len && c2 == -1);
				if (c2 == -1)
					break;

				out.push(String.fromCharCode((c1 << 2) | ((c2 & 0x30) >> 4)));

				/* c3 */
				do {
					c3 = str.charCodeAt(i++) & 0xff;
					if (c3 == 61)
						return _this.UTF8ToUTF16(out.join(''));
					c3 = _const.decodeChars[c3];
				} while (i < len && c3 == -1);
				if (c3 == -1)
					break;

				out.push(String.fromCharCode(((c2 & 0XF) << 4) | ((c3 & 0x3C) >> 2)));

				/* c4 */
				do {
					c4 = str.charCodeAt(i++) & 0xff;
					if (c4 == 61)
						return _this.UTF8ToUTF16(out.join(''));
					c4 = _const.decodeChars[c4];
				} while (i < len && c4 == -1);
				if (c4 == -1)
					break;
				out.push(String.fromCharCode(((c3 & 0x03) << 6) | c4));
			}
			return _this.UTF8ToUTF16(out.join(''));
		}

	};

	lib.utf8 = {

		fromUTF16: function (str) {
			var out = [], i = 0, len = str.length, c;

			while (i < len) {
				c = str.charCodeAt(i);
				if ((c >= 0x0001) && (c <= 0x007F)) {
					out.push(str.charAt(i));
				} else if (c > 0x07FF) {
					out.push(String.fromCharCode(0xE0 | ((c >> 12) & 0x0F)));
					out.push(String.fromCharCode(0x80 | ((c >> 6) & 0x3F)));
					out.push(String.fromCharCode(0x80 | ((c >> 0) & 0x3F)));
				} else {
					out.push(String.fromCharCode(0xC0 | ((c >> 6) & 0x1F)));
					out.push(String.fromCharCode(0x80 | ((c >> 0) & 0x3F)));
				}
				i++;
			}
			return out.join('');
		},

		toUTF16: function (str) {
			var out = [], i = 0, len = str.length, c, char2, char3;

			while (i < len) {
				c = str.charCodeAt(i++);
				switch (c >> 4) {
					case 0: case 1: case 2: case 3: case 4: case 5: case 6: case 7:
						// 0xxxxxxx
						out.push(str.charAt(i - 1));
						break;
					case 12: case 13:
						// 110x xxxx   10xx xxxx
						char2 = str.charCodeAt(i++);
						out.push(String.fromCharCode(((c & 0x1F) << 6) | (char2 & 0x3F)));
						break;
					case 14:
						// 1110 xxxx  10xx xxxx  10xx xxxx
						char2 = str.charCodeAt(i++);
						char3 = str.charCodeAt(i++);
						out.push(String.fromCharCode(((c & 0x0F) << 12) |
							((char2 & 0x3F) << 6) |
							((char3 & 0x3F) << 0)));
						break;
				}
			}

			return out.join('');
		}

	};

  // jshint ignore: start
  // atob & btoa
  var object =
    typeof exports != 'undefined' ? exports :
    typeof self != 'undefined' ? self : // #8: web workers
    $.global; // #31: ExtendScript

  function InvalidCharacterError(message) {
    this.message = message;
  }
  InvalidCharacterError.prototype = new Error();
  InvalidCharacterError.prototype.name = 'InvalidCharacterError';

  // encoder
  // [https://gist.github.com/999166] by [https://github.com/nignag]

  lib.btoa = object.btoa ? (function(input){ return object.btoa(input); }) : (function (input) {
    var str = String(input);
    for (
      // initialize result and counter
      var block, charCode, idx = 0, map = _const.encodeChars, output = '';
      // if the next str index does not exist:
      //   change the mapping table to "="
      //   check if d has no fractional digits
      str.charAt(idx | 0) || (map = '=', idx % 1);
      // "8 - idx % 1 * 8" generates the sequence 2, 4, 6, 8
      output += map.charAt(63 & block >> 8 - idx % 1 * 8)
    ) {
      charCode = str.charCodeAt(idx += 3/4);
      if (charCode > 0xFF) {
        throw new InvalidCharacterError("'btoa' failed: The string to be encoded contains characters outside of the Latin1 range.");
      }
      block = block << 8 | charCode;
    }
    return output;
  });

  // decoder
  // [https://gist.github.com/1020396] by [https://github.com/atk]
  lib.atob = object.atob ? (function(input){ return object.atob(input); }) : (function (input) {
    var str = String(input).replace(/[=]+$/, ''); // #31: ExtendScript bad parse of /=
    if (str.length % 4 == 1) {
      throw new InvalidCharacterError("'atob' failed: The string to be decoded is not correctly encoded.");
    }
    for (
      // initialize result and counters
      var bc = 0, bs, buffer, idx = 0, output = '';
      // get next character
      buffer = str.charAt(idx++);
      // character found in table? initialize bit storage and add its ascii value;
      ~buffer && (bs = bc % 4 ? bs * 64 + buffer : buffer,
        // and if not first of each 4 characters,
        // convert the first 8 bits to one ascii character
        bc++ % 4) ? output += String.fromCharCode(255 & bs >> (-2 * bc & 6)) : 0
    ) {
      // try to find character in table (0-63, not found => -1)
      buffer = _const.encodeChars.indexOf(buffer);
    }
    return output;
  });
	// jshint ignore: end
})(Dynamsoft.Lib);
(function (lib) {

    "use strict";
	
	var _loadjs_ver = 20200717;
	if (lib._loadjs_ver) {
		if (lib._loadjs_ver >= _loadjs_ver) {
			return;
		}
	}
	lib._loadjs_ver = _loadjs_ver;
	
    // load Script / css

    var EMPTY_STR = '',
        TRUE = !0,
        doc = lib.doc,
        docElement = doc && doc.documentElement,
        head = doc.getElementsByTagName('head')[0] || docElement,
        scriptOnload = doc.createElement('script').readyState ?
            function (node, callback) {
                var oldCallback = node.onreadystatechange;
                node.onreadystatechange = function () {
                    var rs = node.readyState;
					node.onreadystatechange = null;
                    if (rs === 'loaded' || rs === 'complete') {
                        if (oldCallback) oldCallback();
                        callback.call(this,true);
                    } else if (rs === 'loading') {
						
					} else {
						callback.call(this,false);
					}
                };
            } :
            function (node, callback) {
                var FALSE = !1;
                node.addEventListener('load', callback, FALSE);
                node.addEventListener('error', callback, FALSE);
            };

    // getScript
    lib.getScript = function (url, isAsync, callback) {
        var node, u;
        if (!lib.isFunction(callback)) {
            callback = function () { };
        }

        if (!lib.isString(url) || url == EMPTY_STR) {
            callback();
            return;
        }

        node = doc.createElement('script');

        u = ['', url].join(EMPTY_STR);
        node.src = u;

        if (isAsync)
            node.async = TRUE;

        node.charset = 'utf-8';

        scriptOnload(node, callback);

        head.insertBefore(node, head.firstChild);

        return node;
    };

    // getScripts
    lib.getScripts = function (urls, isAsync, callback) {
		if (!lib.isArray(urls)) {
            callback();
			return;
        }
		
		var urlLen = urls.length,
			urlCallback = function(o){
				
				if(o)
					urlLen--;
				else
					callback();
				
				if(urlLen <= 0) {
					callback('ok');
				}
			};
		
		lib.each(urls, function (url) {
			lib.getScript(url, isAsync, urlCallback);
		});
		
	};
	
    // getCss
    lib.getCss = function (url, callback) {
        var node, c = callback;

        if (!lib.isFunction(c)) {
            c = !1;
        }
        if (!lib.isString(url) || url == EMPTY_STR) {
            if (c) c();
            return;
        }

        node = doc.createElement('link');

        node.href = url;
        node.rel = 'stylesheet';
        node.async = TRUE;

        if (c) scriptOnload(node, c);

        head.insertBefore(node, head.firstChild);
        return node;
    };

    // getAllCss
    lib.getAllCss = function (cssUrls, cssCallback) {
		if (!lib.isArray(cssUrls)) {
            cssCallback();
			return;
        }
		
		var cssUrlLen = cssUrls.length,
			urlCallback = function(o){
				
				if(o)
					cssUrlLen--;
				else
					cssCallback();
				
				if(cssUrlLen <= 0) {
					cssCallback('ok');
				}
			};
		
		lib.each(cssUrls, function (cssUrl) {
			lib.getCss(cssUrl, urlCallback);
		});
		
	};
	
	lib.addScript = function(jsonScript) {

		var node, sBody;

		sBody = jsonScript.body;
		if (!lib.isString(sBody) || sBody == EMPTY_STR) {
			return;
		}

		node = doc.createElement('script');
		node.charset = 'utf-8';
		
		if(Dynamsoft.navInfoSync.bIE)	// IE
			node.text=sBody;
		else
			node.appendChild(doc.createTextNode(sBody));
		
		if(jsonScript.language)
			node.language = jsonScript.language;
		else
			node.language = 'javascript';
		
		if(jsonScript.type)
			node.type = jsonScript.type;
		else
			node.type = 'text/javascript';

		head.insertBefore(node, head.firstChild);
	};
	
	lib.addJS = function(javaScript) {
		lib.addScript({body:javaScript});
	};
	lib.addVBS = function(vbScript) {
		lib.addScript({body:vbScript, language:'vbscript', type:'text/vbscript'});
	};
})(Dynamsoft.Lib);
(function(dynam){

	"use strict";

	var lib = dynam.Lib,
		_asyncQueue_ver = 20200521;
		
	if (lib._asyncQueue_ver) {
		if (lib.isNumber(lib._asyncQueue_ver) && lib._asyncQueue_ver >= _asyncQueue_ver) {
			return;
		}
	}
	lib._asyncQueue_ver = _asyncQueue_ver;
	
	var asyncQueue = {
		queue: [],
		doNextStarted : false,
		timer: false,
		
		pushToDo : function(_obj, _method, _args){
			asyncQueue.queue.push({
				obj: _obj,
				method: _method,
				args: _args
			});
		},
		
		doNext : function (){
			if(!asyncQueue.doNextStarted) {
				clearTimeout(asyncQueue.timer);
				asyncQueue.timer=false;
				return;
			}
			
			if(asyncQueue.queue.length == 0){
				asyncQueue.timer = setTimeout(asyncQueue.doNext, 500);
				return;
			}
		
			var cmd = asyncQueue.queue[0],
				obj=cmd.obj,
				method=cmd.method,
				args=cmd.args;
				
			asyncQueue.queue.splice(0, 1);
			
			if(lib.isFunction(obj[method])) {
				if(args.length>2){
					var s1 = args[args.length - 2], 
						f1 = args[args.length - 1];
					args[args.length - 2] = function(){
						try{
							s1.apply(obj, arguments);
						}catch(e){}
						asyncQueue.timer = setTimeout(asyncQueue.doNext, 0);
					};
					
					args[args.length - 1] = function(){
						try{
							f1.apply(obj, arguments);
						}catch(e){}
						asyncQueue.timer = setTimeout(asyncQueue.doNext, 0);
					};
				}
				
				try{
					obj[method].apply(obj, args);
				}catch(e2){}
				
				return;
			}
			else {
				lib.log('not invoke a function: ' + method);
				asyncQueue.timer = setTimeout(asyncQueue.doNext, 0);
			}
		},

		start : function(){
			if(!asyncQueue.doNextStarted) {
				asyncQueue.doNextStarted = true;
				asyncQueue.timer = setTimeout(asyncQueue.doNext, 0);
			}
		},
		
		stop : function(){
			clearTimeout(asyncQueue.timer);
			asyncQueue.doNextStarted = false;
			asyncQueue.queue = [];
		}
	};
	
	lib.asyncQueue = asyncQueue;
	
})(Dynamsoft);
/* global window, exports, define */

(function(lib) {
    'use strict';

    var _sprintf_ver = 20200521;
    if (lib._sprintf_ver) {
        if (lib._sprintf_ver >= _sprintf_ver) {
            return;
        }
    }
    lib._sprintf_ver = _sprintf_ver;
	
    var sprintf, re = {
        not_string: /[^s]/,
        not_bool: /[^t]/,
        not_type: /[^T]/,
        not_primitive: /[^v]/,
        number: /[diefg]/,
        numeric_arg: /[bcdiefguxX]/,
        json: /[j]/,
        not_json: /[^j]/,
        text: /^[^\x25]+/,
        modulo: /^\x25{2}/,
        placeholder: /^\x25(?:([1-9]\d*)\$|\(([^)]+)\))?(\+)?(0|'[^$])?(-)?(\d+)?(?:\.(\d+))?([b-gijostTuvxX])/,
        key: /^([a-z_][a-z_\d]*)/i,
        key_access: /^\.([a-z_][a-z_\d]*)/i,
        index_access: /^\[(\d+)\]/,
        sign: /^[+-]/
    };
	
	function sprintf_repeat(str, times) {
		if('_'.repeat) {
			return str.repeat(times);
		}
		
		var i=0, tmp=[];
		for(;i<times;i++)
			tmp.push(str);
		return tmp.join('');
	}

    function sprintf_format(parse_tree, argv) {
        var cursor = 1, tree_length = parse_tree.length, arg, output = '', i, k, ph, pad, pad_character, pad_length, is_positive, sign;
		
        for (i = 0; i < tree_length; i++) {
            if (typeof parse_tree[i] === 'string') {
                output += parse_tree[i];
            }
            else if (typeof parse_tree[i] === 'object') {
                ph = parse_tree[i]; // convenience purposes only
                if (ph.keys) { // keyword argument
                    arg = argv[cursor];
                    for (k = 0; k < ph.keys.length; k++) {
                        if (arg == undefined) {
                            throw new Error(sprintf('[sprintf] Cannot access property "%s" of undefined value "%s"', ph.keys[k], ph.keys[k-1]));
                        }
                        arg = arg[ph.keys[k]];
                    }
                }
                else if (ph.param_no) { // positional argument (explicit)
                    arg = argv[ph.param_no];
                }
                else { // positional argument (implicit)
                    arg = argv[cursor++];
                }

                if (re.not_type.test(ph.type) && re.not_primitive.test(ph.type) && arg instanceof Function) {
                    arg = arg();
                }

                if (re.numeric_arg.test(ph.type) && (typeof arg !== 'number' && isNaN(arg))) {
                    throw new TypeError(sprintf('[sprintf] expecting number but found %T', arg));
                }

                if (re.number.test(ph.type)) {
                    is_positive = arg >= 0;
                }

                switch (ph.type) {
                    case 'b':
                        arg = parseInt(arg, 10).toString(2);
                        break;
                    case 'c':
                        arg = String.fromCharCode(parseInt(arg, 10));
                        break;
                    case 'd':
                    case 'i':
                        arg = parseInt(arg, 10);
                        break;
                    case 'j':
                        arg = JSON.stringify(arg, null, ph.width ? parseInt(ph.width) : 0);
                        break;
                    case 'e':
                        arg = ph.precision ? parseFloat(arg).toExponential(ph.precision) : parseFloat(arg).toExponential();
                        break;
                    case 'f':
                        arg = ph.precision ? parseFloat(arg).toFixed(ph.precision) : parseFloat(arg);
                        break;
                    case 'g':
                        arg = ph.precision ? String(Number(arg.toPrecision(ph.precision))) : parseFloat(arg);
                        break;
                    case 'o':
                        arg = (parseInt(arg, 10) >>> 0).toString(8);
                        break;
                    case 's':
                        arg = String(arg);
                        arg = (ph.precision ? arg.substring(0, ph.precision) : arg);
                        break;
                    case 't':
                        arg = String(!!arg);
                        arg = (ph.precision ? arg.substring(0, ph.precision) : arg);
                        break;
                    case 'T':
                        arg = Object.prototype.toString.call(arg).slice(8, -1).toLowerCase();
                        arg = (ph.precision ? arg.substring(0, ph.precision) : arg);
                        break;
                    case 'u':
                        arg = parseInt(arg, 10) >>> 0;
                        break;
                    case 'v':
                        arg = arg.valueOf();
                        arg = (ph.precision ? arg.substring(0, ph.precision) : arg);
                        break;
                    case 'x':
                        arg = (parseInt(arg, 10) >>> 0).toString(16);
                        break;
                    case 'X':
                        arg = (parseInt(arg, 10) >>> 0).toString(16).toUpperCase();
                        break;
                }
                if (re.json.test(ph.type)) {
                    output += arg;
                }
                else {
                    if (re.number.test(ph.type) && (!is_positive || ph.sign)) {
                        sign = is_positive ? '+' : '-';
                        arg = arg.toString().replace(re.sign, '');
                    }
                    else {
                        sign = '';
                    }
                    pad_character = ph.pad_char ? ph.pad_char === '0' ? '0' : ph.pad_char.charAt(1) : ' ';
                    pad_length = ph.width - (sign + arg).length;
                    pad = ph.width ? (pad_length > 0 ? sprintf_repeat(pad_character,pad_length) : '') : '';
                    output += ph.align ? sign + arg + pad : (pad_character === '0' ? sign + pad + arg : pad + sign + arg);
                }
            }
        }
        return output;
    }

    var sprintf_cache = Object.create ? Object.create(null) : {};

    function sprintf_parse(fmt) {
        if (sprintf_cache[fmt]) {
            return sprintf_cache[fmt];
        }

        var _fmt = fmt, match, parse_tree = [], arg_names = 0;
        while (_fmt) {
            if ((match = re.text.exec(_fmt)) !== null) {
                parse_tree.push(match[0]);
            }
            else if ((match = re.modulo.exec(_fmt)) !== null) {
                parse_tree.push('%');
            }
            else if ((match = re.placeholder.exec(_fmt)) !== null) {
                if (match[2]) {
                    arg_names |= 1;
                    var field_list = [], replacement_field = match[2], field_match = [];
                    if ((field_match = re.key.exec(replacement_field)) !== null) {
                        field_list.push(field_match[1]);
                        while ((replacement_field = replacement_field.substring(field_match[0].length)) !== '') {
                            if ((field_match = re.key_access.exec(replacement_field)) !== null) {
                                field_list.push(field_match[1]);
                            }
                            else if ((field_match = re.index_access.exec(replacement_field)) !== null) {
                                field_list.push(field_match[1]);
                            }
                            else {
                                throw new SyntaxError('[sprintf] failed to parse named argument key');
                            }
                        }
                    }
                    else {
                        throw new SyntaxError('[sprintf] failed to parse named argument key');
                    }
                    match[2] = field_list;
                }
                else {
                    arg_names |= 2;
                }
                if (arg_names === 3) {
                    throw new Error('[sprintf] mixing positional and named placeholders is not (yet) supported');
                }

                parse_tree.push(
                    {
                        placeholder: match[0],
                        param_no:    match[1],
                        keys:        match[2],
                        sign:        match[3],
                        pad_char:    match[4],
                        align:       match[5],
                        width:       match[6],
                        precision:   match[7],
                        type:        match[8]
                    }
                );
            }
            else {
                throw new SyntaxError('[sprintf] unexpected placeholder');
            }
            _fmt = _fmt.substring(match[0].length);
        }
        sprintf_cache[fmt] = parse_tree;
		return parse_tree;
    }

	
    sprintf = function (key) {
        // `arguments` is not an array, but should be fine for this call
        return sprintf_format(sprintf_parse(key), arguments);
    };

    function vsprintf(fmt, argv) {
        return sprintf.apply(null, [fmt].concat(argv || []));
    }

	lib.sprintf = sprintf;
	lib.vsprintf = vsprintf;
	
})(Dynamsoft.Lib);
